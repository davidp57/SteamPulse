"""Light HTTP sidecar: serves the static HTML pages and exposes a small mutation API.

When running ``steam-serve``, users open the library in a browser via
``http://localhost:<port>/`` rather than as a local file.  The sidecar exposes
a small REST-ish API so the rendered pages can perform data mutations
(soft-delete, reactivate, hard-delete) directly from the UI.

The HTML pages degrade gracefully: if ``steam-serve`` is not running they
remain fully functional read-only dashboards.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import re
import subprocess
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import __version__
from .config import get_config_path, load_config
from .db import Database
from .models import SYNTHETIC_APPID_BASE
from .renderer import write_alerts_html, write_diagnostic_html, write_html

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PORT: int = 8080

_ROUTE_PING = "/api/ping"
_ROUTE_MARK_REMOVED = re.compile(r"^/api/mark-removed/(\d+)$")
_ROUTE_MARK_ACTIVE = re.compile(r"^/api/mark-active/(\d+)$")
_ROUTE_DELETE = re.compile(r"^/api/delete/(\d+)$")

# Only allow plain filenames — no path traversal, no directories.
_SAFE_FILENAME = re.compile(r"^[\w\-. ]+\.html$")

# Pages that require authentication when a token is configured.
_PROTECTED_PAGES: frozenset[str] = frozenset({"steam_diagnostic.html"})

_COOKIE_NAME: str = "sp_session"
_ROUTE_LOGIN: str = "/login"
_ROUTE_LOGOUT: str = "/api/logout"
_ROUTE_RERENDER: str = "/api/rerender"
_ROUTE_REFETCH: str = "/api/refetch"

# Strip ANSI colour codes and carriage-returns from subprocess output.
_ANSI_ESCAPE: re.Pattern[str] = re.compile(r"\x1b\[[0-9;]*[mGKHF]")

# Minimal self-contained login page.  $FORM_ERROR$ is replaced at runtime.
_LOGIN_PAGE: str = """\
<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>SteamPulse \u2013 Login</title><style>
body {
  margin: 0; display: flex; align-items: center; justify-content: center;
  min-height: 100vh; background: #13191f; color: #c8d8ef;
  font-family: system-ui, sans-serif;
}
.box {
  background: #111722; border: 1px solid #1f2d45; border-radius: 12px;
  padding: 2rem 2.5rem; max-width: 340px; width: 100%;
}
h2 { margin: 0 0 1.4rem; color: #1db9ff; font-size: 1.1rem; }
input {
  display: block; width: 100%; box-sizing: border-box;
  padding: .55rem .75rem; border: 1px solid #1f2d45; border-radius: 6px;
  background: #0a0e14; color: #c8d8ef; font-size: .9rem;
  margin-bottom: .9rem;
}
button {
  width: 100%; padding: .6rem; background: #1db9ff; border: none;
  border-radius: 6px; font-size: .9rem; font-weight: 600;
  color: #0a0e14; cursor: pointer;
}
button:hover { background: #48caff; }
.err { color: #e44; font-size: .8rem; margin-bottom: .8rem; }
</style></head>
<body><div class="box"><h2>&#128273; SteamPulse</h2>
$FORM_ERROR$<form method="POST" action="/login">
<input type="password" name="token" placeholder="Access token"
       autofocus autocomplete="current-password">
<button type="submit">Login</button></form>
</div></body></html>"""


# ---------------------------------------------------------------------------
# Re-render helper
# ---------------------------------------------------------------------------


def _rerender(db: Database, steamid: str, output_dir: Path, lang: str | None) -> None:
    """Re-render all HTML pages after a mutation.

    Does nothing when *steamid* is empty (no credentials configured).

    Args:
        db: Open database instance.
        steamid: User's SteamID64.  Skipped when empty string.
        output_dir: Directory containing the HTML output files.
        lang: Language code (or None for system default).
    """
    if not steamid:
        return
    records = db.get_all_game_records()
    lib_path = output_dir / "steam_library.html"
    alerts_path = output_dir / "steam_alerts.html"
    diag_path = output_dir / "steam_diagnostic.html"
    unknown_games = [
        r for r in records if r.game.appid >= SYNTHETIC_APPID_BASE or r.status.badge == "unknown"
    ]
    write_html(
        records,
        steamid,
        lib_path,
        alerts_href=alerts_path.name,
        diag_href=diag_path.name,
        lang=lang,
    )
    write_alerts_html(
        db.get_alerts(),
        records,
        steamid,
        alerts_path,
        library_href=lib_path.name,
        diag_href=diag_path.name,
        lang=lang,
    )
    write_diagnostic_html(
        db.get_diagnostic_summary(),
        db.get_all_appid_mappings(),
        diag_path,
        unknown_games=unknown_games,
        library_href=lib_path.name,
        alerts_href=alerts_path.name,
        lang=lang,
    )


def _build_fetch_cmd(config_path: Path | None, db_path: Path) -> list[str]:
    """Build the subprocess command that runs cmd_fetch inside this environment.

    Uses ``sys.executable`` so the correct virtualenv Python and installed
    package are always picked up, regardless of PATH.

    Args:
        config_path: Path to the TOML config file, or ``None`` for the
            platform default.
        db_path: Path to the SQLite database file.

    Returns:
        A list suitable for :class:`subprocess.Popen`.
    """
    argv: list[str] = ["steam-fetch"]
    if config_path is not None:
        argv += ["--config", str(config_path)]
    argv += ["--db", str(db_path)]
    script = (
        f"import sys; sys.argv = {argv!r}; from steam_tracker.cli import cmd_fetch; cmd_fetch()"
    )
    return [sys.executable, "-c", script]


# ---------------------------------------------------------------------------
# Request handler factory
# ---------------------------------------------------------------------------


def make_handler(
    db_path: Path,
    output_dir: Path,
    steamid: str,
    lang: str | None,
    token: str | None = None,
    config_path: Path | None = None,
) -> type[BaseHTTPRequestHandler]:
    """Return a handler class bound to the given server configuration.

    Using a factory avoids global state and keeps context close to the handler.

    Args:
        db_path: Path to the SQLite database file.
        output_dir: Directory containing the HTML output files.
        steamid: User's SteamID64 (needed for re-renders).
        lang: Language code (or None for system default).
        token: Shared secret for authentication.  When ``None``, auth is
            disabled and all routes are publicly accessible.
        config_path: Path to the TOML config file used when re-fetching via
            ``/api/refetch``.  Falls back to the platform default when
            ``None``.

    Returns:
        A :class:`BaseHTTPRequestHandler` subclass with config baked in.
    """
    # One lock per server instance — prevents concurrent fetch runs.
    _fetch_lock = threading.Lock()

    class _Handler(BaseHTTPRequestHandler):
        # ── logging ──────────────────────────────────────────────────────────

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            log.debug(format, *args)

        # ── auth helpers ─────────────────────────────────────────────────────

        def _is_authenticated(self) -> bool:
            """Return True when the request carries a valid session cookie."""
            if not token:
                return True  # auth disabled
            raw_cookies = self.headers.get("Cookie", "")
            for part in raw_cookies.split(";"):
                k, _, v = part.strip().partition("=")
                if k.strip() == _COOKIE_NAME and hmac.compare_digest(v.strip(), token):
                    return True
            return False

        def _send_redirect(self, location: str) -> None:
            """Send a 302 redirect response."""
            self.send_response(302)
            self.send_header("Location", location)
            self.end_headers()

        def _set_session_cookie(self) -> None:
            """Append a Set-Cookie header that establishes the session."""
            assert token is not None
            self.send_header(
                "Set-Cookie",
                f"{_COOKIE_NAME}={token}; HttpOnly; SameSite=Strict; Path=/",
            )

        def _clear_session_cookie(self) -> None:
            """Append a Set-Cookie header that expires the session."""
            self.send_header(
                "Set-Cookie",
                f"{_COOKIE_NAME}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0",
            )

        def _serve_login_page(self, error: str = "") -> None:
            """Send the HTML login form, optionally with an error message."""
            body = _LOGIN_PAGE.replace("$FORM_ERROR$", error).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        # ── response helpers ─────────────────────────────────────────────────

        def _send_json(self, code: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _not_found(self) -> None:
            self._send_json(404, {"ok": False, "error": "not found"})

        # ── GET ──────────────────────────────────────────────────────────────

        def do_GET(self) -> None:
            """Handle GET requests: ping, login, logout, static HTML, root redirect."""
            path = self.path.split("?")[0]

            if path in ("", "/"):
                self._send_redirect("/steam_library.html")
                return

            if path == _ROUTE_PING:
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "version": __version__,
                        "auth_enabled": token is not None,
                        "authenticated": self._is_authenticated(),
                    },
                )
                return

            if path == _ROUTE_LOGIN:
                self._serve_login_page()
                return

            if path == _ROUTE_LOGOUT:
                self.send_response(302)
                self._clear_session_cookie()
                self.send_header("Location", "/")
                self.end_headers()
                return

            if path == _ROUTE_REFETCH:
                if token and not self._is_authenticated():
                    self._send_json(401, {"ok": False, "error": "authentication required"})
                    return
                if not _fetch_lock.acquire(blocking=False):
                    self._send_json(409, {"ok": False, "error": "fetch already running"})
                    return
                try:
                    # Pre-flight: check that Steam credentials exist in the config.
                    try:
                        _effective_path = config_path or get_config_path()
                        _cfg = load_config(_effective_path)
                        if not _cfg.get("key") or not _cfg.get("steamid"):
                            self.send_response(200)
                            self.send_header("Content-Type", "text/event-stream")
                            self.send_header("Cache-Control", "no-cache")
                            self.end_headers()
                            _msg = "\u26a0 No Steam credentials. Run 'steam-setup' first."
                            _err = json.dumps({"msg": _msg})
                            _done = json.dumps({"done": True, "status": "error"})
                            self.wfile.write(f"data: {_err}\n\ndata: {_done}\n\n".encode())
                            return
                        # Start SSE stream — this thread blocks until fetch completes.
                        self.send_response(200)
                        self.send_header("Content-Type", "text/event-stream")
                        self.send_header("Cache-Control", "no-cache")
                        self.send_header("Connection", "keep-alive")
                        self.send_header("X-Accel-Buffering", "no")
                        self.end_headers()
                    except Exception as _pre_exc:
                        log.error("refetch pre-flight failed: %s", _pre_exc)
                        self._send_json(500, {"ok": False, "error": str(_pre_exc)})
                        return
                    try:
                        cmd = _build_fetch_cmd(config_path, db_path)
                        _env = os.environ.copy()
                        _env["PYTHONUTF8"] = "1"
                        proc = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL,
                            text=True,
                            encoding="utf-8",
                            bufsize=1,
                            env=_env,
                        )
                        ok = True
                        assert proc.stdout is not None
                        try:
                            for raw_line in proc.stdout:
                                line = _ANSI_ESCAPE.sub("", raw_line).split("\r")[-1].strip()
                                if line:
                                    _data = json.dumps({"msg": line})
                                    self.wfile.write(f"data: {_data}\n\n".encode())
                                    self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            proc.kill()
                            return
                        proc.wait()
                        ok = proc.returncode == 0
                        if ok:
                            _data = json.dumps({"msg": "\U0001f3a8 Rendering HTML pages..."})
                            self.wfile.write(f"data: {_data}\n\n".encode())
                            self.wfile.flush()
                            try:
                                _rerender(Database(db_path), steamid, output_dir, lang)
                            except Exception as _exc:
                                ok = False
                                log.error("re-render after fetch failed: %s", _exc)
                        _status = "ok" if ok else "error"
                        _done = json.dumps({"done": True, "status": _status})
                        self.wfile.write(f"data: {_done}\n\n".encode())
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                finally:
                    _fetch_lock.release()
                return
            if path.endswith(".html"):
                filename = path.lstrip("/")
                if not _SAFE_FILENAME.match(filename):
                    self._not_found()
                    return
                # Protected pages require authentication
                if token and filename in _PROTECTED_PAGES and not self._is_authenticated():
                    self._send_redirect("/login")
                    return
                file_path = output_dir / filename
                if not file_path.exists():
                    self._not_found()
                    return
                content = file_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

            self._not_found()

        # ── POST ─────────────────────────────────────────────────────────────

        def do_POST(self) -> None:
            """Handle POST requests: login, mark-removed, mark-active, delete."""
            path = self.path.split("?")[0]

            if path == _ROUTE_LOGIN:
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(max(0, length)).decode(errors="replace")
                params = urllib.parse.parse_qs(raw)
                submitted = (params.get("token") or [""])[0]
                if token and hmac.compare_digest(submitted, token):
                    self.send_response(302)
                    self._set_session_cookie()
                    self.send_header("Location", "/")
                    self.end_headers()
                else:
                    self._serve_login_page('<p class="err">Invalid token.</p>')
                return

            # All mutation endpoints require authentication
            if token and not self._is_authenticated():
                self._send_json(401, {"ok": False, "error": "authentication required"})
                return

            if path == _ROUTE_RERENDER:
                _db = Database(db_path)
                try:
                    _rerender(_db, steamid, output_dir, lang)
                    self._send_json(200, {"ok": True})
                except Exception as _exc:
                    log.error("rerender failed: %s", _exc)
                    self._send_json(500, {"ok": False, "error": str(_exc)})
            elif m := _ROUTE_MARK_REMOVED.match(path):
                appid = int(m.group(1))
                db = Database(db_path)
                changed = db.mark_removed({appid})
                if changed:
                    _rerender(db, steamid, output_dir, lang)
                self._send_json(200, {"ok": True, "appid": appid, "changed": changed})
            elif m := _ROUTE_MARK_ACTIVE.match(path):
                appid = int(m.group(1))
                db = Database(db_path)
                changed = db.mark_active({appid})
                if changed:
                    _rerender(db, steamid, output_dir, lang)
                self._send_json(200, {"ok": True, "appid": appid, "changed": changed})
            elif m := _ROUTE_DELETE.match(path):
                appid = int(m.group(1))
                db = Database(db_path)
                changed = db.delete_games({appid})
                if changed == 0:
                    self._send_json(404, {"ok": False, "error": "not found", "appid": appid})
                else:
                    _rerender(db, steamid, output_dir, lang)
                    self._send_json(200, {"ok": True, "appid": appid, "changed": changed})
            else:
                self._not_found()

    return _Handler


# ---------------------------------------------------------------------------
# Public server entry point
# ---------------------------------------------------------------------------


_TOKEN_RE: re.Pattern[str] = re.compile(r"^[A-Za-z0-9_\-]+$")


def run_server(
    db_path: Path,
    output_dir: Path,
    steamid: str,
    lang: str | None = None,
    port: int = DEFAULT_PORT,
    host: str = "127.0.0.1",
    token: str | None = None,
    config_path: Path | None = None,
) -> None:
    """Start the SteamPulse sidecar server and block until Ctrl+C.

    Args:
        db_path: Path to the SQLite database file.
        output_dir: Directory containing the HTML output files.
        steamid: User's SteamID64 (used when re-rendering after mutations).
        lang: Language code (or None for system default).
        port: TCP port to listen on.
        host: Interface to bind to (default: ``127.0.0.1`` — loopback only).
            Pass ``0.0.0.0`` to expose on all interfaces.
        token: Shared secret enabling auth mode.  Must contain only
            URL-safe characters (``A-Za-z0-9_-``).  When ``None``, all routes
            are publicly accessible.
        config_path: Path to the TOML config file.  Forwarded to the handler
            so that ``/api/refetch`` can invoke ``cmd_fetch`` with the correct
            credentials.  When ``None``, falls back to the platform default.

    Raises:
        KeyboardInterrupt: Propagated; caller should handle it.
        ValueError: If ``token`` contains invalid characters.
    """
    if token is not None and not _TOKEN_RE.fullmatch(token):
        raise ValueError("--token must contain only A-Za-z0-9, underscore, or hyphen characters.")
    handler_cls = make_handler(
        db_path, output_dir, steamid, lang, token=token, config_path=config_path
    )
    with ThreadingHTTPServer((host, port), handler_cls) as httpd:
        log.info("SteamPulse sidecar listening on %s:%d", host, port)
        httpd.serve_forever()
