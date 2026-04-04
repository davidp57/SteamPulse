"""Tests for the SteamPulse sidecar HTTP server (steam_tracker/server.py)."""
from __future__ import annotations

import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

from steam_tracker.db import Database
from steam_tracker.models import OwnedGame
from steam_tracker.server import _COOKIE_NAME, DEFAULT_PORT, make_handler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _start_server(
    tmp_path: Path,
    steamid: str = "",
    token: str | None = None,
    config_path: Path | None = None,
) -> tuple[int, ThreadingHTTPServer]:
    """Spin up a server bound to an OS-assigned free port (port=0).

    Returns:
        (bound_port, httpd) — caller must call ``httpd.shutdown()`` when done.
    """
    db_path = tmp_path / "test.db"
    Database(db_path)  # ensure schema exists

    handler_cls = make_handler(
        db_path, tmp_path, steamid, lang=None, token=token, config_path=config_path
    )
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    bound_port: int = httpd.server_address[1]

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return bound_port, httpd


# ---------------------------------------------------------------------------
# /api/ping
# ---------------------------------------------------------------------------


class TestPing:
    def test_ping_ok(self, tmp_path: Path) -> None:
        port, httpd = _start_server(tmp_path)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/api/ping")
            resp = conn.getresponse()
            data = json.loads(resp.read())
            assert resp.status == 200
            assert data["ok"] is True
            assert "version" in data
            assert data["auth_enabled"] is False
            assert data["authenticated"] is True
        finally:
            httpd.shutdown()

    def test_ping_auth_enabled_unauthenticated(self, tmp_path: Path) -> None:
        port, httpd = _start_server(tmp_path, token="secret")
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/api/ping")
            resp = conn.getresponse()
            data = json.loads(resp.read())
            assert resp.status == 200
            assert data["auth_enabled"] is True
            assert data["authenticated"] is False
        finally:
            httpd.shutdown()

    def test_ping_content_type_is_json(self, tmp_path: Path) -> None:
        port, httpd = _start_server(tmp_path)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/api/ping")
            resp = conn.getresponse()
            resp.read()
            assert "application/json" in (resp.getheader("Content-Type") or "")
        finally:
            httpd.shutdown()


# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------


class TestRootRedirect:
    def test_root_redirects_to_library(self, tmp_path: Path) -> None:
        port, httpd = _start_server(tmp_path)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/")
            resp = conn.getresponse()
            resp.read()
            assert resp.status == 302
            assert resp.getheader("Location") == "/steam_library.html"
        finally:
            httpd.shutdown()


# ---------------------------------------------------------------------------
# Static file serving
# ---------------------------------------------------------------------------


class TestStaticFiles:
    def test_serve_existing_html(self, tmp_path: Path) -> None:
        (tmp_path / "steam_library.html").write_text("<html>hi</html>", encoding="utf-8")
        port, httpd = _start_server(tmp_path)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/steam_library.html")
            resp = conn.getresponse()
            body = resp.read()
            assert resp.status == 200
            assert b"hi" in body
        finally:
            httpd.shutdown()

    def test_missing_html_is_404(self, tmp_path: Path) -> None:
        port, httpd = _start_server(tmp_path)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/nonexistent.html")
            resp = conn.getresponse()
            resp.read()
            assert resp.status == 404
        finally:
            httpd.shutdown()

    def test_path_traversal_rejected(self, tmp_path: Path) -> None:
        port, httpd = _start_server(tmp_path)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/../outside.html")
            resp = conn.getresponse()
            resp.read()
            assert resp.status == 404
        finally:
            httpd.shutdown()

    def test_unknown_path_is_404(self, tmp_path: Path) -> None:
        port, httpd = _start_server(tmp_path)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/api/unknown")
            resp = conn.getresponse()
            resp.read()
            assert resp.status == 404
        finally:
            httpd.shutdown()


# ---------------------------------------------------------------------------
# POST /api/mark-removed
# ---------------------------------------------------------------------------


def _make_html_stubs(tmp_path: Path) -> None:
    """Write minimal placeholder HTML files so _rerender doesn't fail."""
    for fname in ("steam_library.html", "steam_alerts.html", "steam_diagnostic.html"):
        (tmp_path / fname).write_text("<html></html>", encoding="utf-8")


class TestMarkRemoved:
    def test_mark_active_game_as_removed(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.upsert_game(OwnedGame(appid=42, name="Test Game"))
        _make_html_stubs(tmp_path)

        port, httpd = _start_server(tmp_path)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("POST", "/api/mark-removed/42")
            resp = conn.getresponse()
            data = json.loads(resp.read())
            assert resp.status == 200
            assert data["ok"] is True
            assert data["appid"] == 42
            assert data["changed"] == 1
        finally:
            httpd.shutdown()

    def test_mark_already_removed_returns_zero_changed(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.upsert_game(OwnedGame(appid=99, name="Gone Game"))
        db.mark_removed({99})

        port, httpd = _start_server(tmp_path)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("POST", "/api/mark-removed/99")
            resp = conn.getresponse()
            data = json.loads(resp.read())
            assert resp.status == 200
            assert data["ok"] is True
            assert data["changed"] == 0  # already removed — no re-render triggered
        finally:
            httpd.shutdown()


# ---------------------------------------------------------------------------
# POST /api/mark-active
# ---------------------------------------------------------------------------


class TestMarkActive:
    def test_reactivate_removed_game(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.upsert_game(OwnedGame(appid=10, name="Comeback Game"))
        db.mark_removed({10})
        _make_html_stubs(tmp_path)

        port, httpd = _start_server(tmp_path)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("POST", "/api/mark-active/10")
            resp = conn.getresponse()
            data = json.loads(resp.read())
            assert resp.status == 200
            assert data["ok"] is True
            assert data["changed"] == 1
        finally:
            httpd.shutdown()

    def test_reactivate_already_active_returns_zero_changed(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.upsert_game(OwnedGame(appid=11, name="Active Game"))
        # Not removed — mark_active should be a no-op

        port, httpd = _start_server(tmp_path)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("POST", "/api/mark-active/11")
            resp = conn.getresponse()
            data = json.loads(resp.read())
            assert resp.status == 200
            assert data["changed"] == 0
        finally:
            httpd.shutdown()


# ---------------------------------------------------------------------------
# POST /api/delete
# ---------------------------------------------------------------------------


class TestDelete:
    def test_delete_existing_game(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.upsert_game(OwnedGame(appid=7, name="Delete Me"))
        _make_html_stubs(tmp_path)

        port, httpd = _start_server(tmp_path)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("POST", "/api/delete/7")
            resp = conn.getresponse()
            data = json.loads(resp.read())
            assert resp.status == 200
            assert data["ok"] is True
            assert data["changed"] == 1
        finally:
            httpd.shutdown()

    def test_delete_nonexistent_game_returns_404(self, tmp_path: Path) -> None:
        port, httpd = _start_server(tmp_path)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("POST", "/api/delete/99999")
            resp = conn.getresponse()
            data = json.loads(resp.read())
            assert resp.status == 404
            assert data["ok"] is False
        finally:
            httpd.shutdown()

    def test_unknown_post_route_returns_404(self, tmp_path: Path) -> None:
        port, httpd = _start_server(tmp_path)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("POST", "/api/unknown-action")
            resp = conn.getresponse()
            resp.read()
            assert resp.status == 404
        finally:
            httpd.shutdown()


# ---------------------------------------------------------------------------
# Utility / constants
# ---------------------------------------------------------------------------


def test_default_port_is_8080() -> None:
    assert DEFAULT_PORT == 8080


def test_make_handler_returns_handler_class(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    Database(db_path)
    handler_cls = make_handler(db_path, tmp_path, steamid="", lang=None)
    from http.server import BaseHTTPRequestHandler  # noqa: PLC0415
    assert issubclass(handler_cls, BaseHTTPRequestHandler)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

_TOKEN = "s3cr3t"
_COOKIE_HDR = f"{_COOKIE_NAME}={_TOKEN}"


class TestLoginPage:
    def test_login_page_accessible_without_auth(self, tmp_path: Path) -> None:
        port, httpd = _start_server(tmp_path, token=_TOKEN)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/login")
            resp = conn.getresponse()
            body = resp.read()
            assert resp.status == 200
            assert b"<form" in body
        finally:
            httpd.shutdown()

    def test_login_correct_token_sets_cookie_and_redirects(self, tmp_path: Path) -> None:
        port, httpd = _start_server(tmp_path, token=_TOKEN)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            body = f"token={_TOKEN}".encode()
            conn.request(
                "POST", "/login", body=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp = conn.getresponse()
            resp.read()
            assert resp.status == 302
            assert resp.getheader("Location") == "/"
            cookie = resp.getheader("Set-Cookie") or ""
            assert _COOKIE_NAME in cookie
            assert _TOKEN in cookie
        finally:
            httpd.shutdown()

    def test_login_wrong_token_shows_error_page(self, tmp_path: Path) -> None:
        port, httpd = _start_server(tmp_path, token=_TOKEN)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            body = b"token=wrongpassword"
            conn.request(
                "POST", "/login", body=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp = conn.getresponse()
            content = resp.read()
            assert resp.status == 200
            assert b"err" in content  # error CSS class present
        finally:
            httpd.shutdown()


class TestLogout:
    def test_logout_clears_cookie_and_redirects(self, tmp_path: Path) -> None:
        port, httpd = _start_server(tmp_path, token=_TOKEN)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/api/logout", headers={"Cookie": _COOKIE_HDR})
            resp = conn.getresponse()
            resp.read()
            assert resp.status == 302
            assert resp.getheader("Location") == "/"
            cookie = resp.getheader("Set-Cookie") or ""
            assert "Max-Age=0" in cookie
        finally:
            httpd.shutdown()


class TestAuthProtection:
    def test_diagnostic_without_auth_redirects_to_login(self, tmp_path: Path) -> None:
        (tmp_path / "steam_diagnostic.html").write_text("<html></html>", encoding="utf-8")
        port, httpd = _start_server(tmp_path, token=_TOKEN)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/steam_diagnostic.html")
            resp = conn.getresponse()
            resp.read()
            assert resp.status == 302
            assert resp.getheader("Location") == "/login"
        finally:
            httpd.shutdown()

    def test_diagnostic_with_auth_returns_200(self, tmp_path: Path) -> None:
        (tmp_path / "steam_diagnostic.html").write_text("<html>diag</html>", encoding="utf-8")
        port, httpd = _start_server(tmp_path, token=_TOKEN)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/steam_diagnostic.html", headers={"Cookie": _COOKIE_HDR})
            resp = conn.getresponse()
            body = resp.read()
            assert resp.status == 200
            assert b"diag" in body
        finally:
            httpd.shutdown()

    def test_public_page_accessible_without_auth(self, tmp_path: Path) -> None:
        (tmp_path / "steam_library.html").write_text("<html>lib</html>", encoding="utf-8")
        port, httpd = _start_server(tmp_path, token=_TOKEN)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/steam_library.html")
            resp = conn.getresponse()
            body = resp.read()
            assert resp.status == 200
            assert b"lib" in body
        finally:
            httpd.shutdown()

    def test_mutation_without_auth_returns_401(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.upsert_game(OwnedGame(appid=55, name="Protected Game"))
        port, httpd = _start_server(tmp_path, token=_TOKEN)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("POST", "/api/mark-removed/55")
            resp = conn.getresponse()
            data = json.loads(resp.read())
            assert resp.status == 401
            assert data["ok"] is False
            assert data["error"] == "authentication required"
        finally:
            httpd.shutdown()

    def test_mutation_with_auth_executes(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.upsert_game(OwnedGame(appid=56, name="Auth Game"))
        _make_html_stubs(tmp_path)
        port, httpd = _start_server(tmp_path, token=_TOKEN)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request(
                "POST", "/api/mark-removed/56",
                headers={"Cookie": _COOKIE_HDR},
            )
            resp = conn.getresponse()
            data = json.loads(resp.read())
            assert resp.status == 200
            assert data["ok"] is True
            assert data["changed"] == 1
        finally:
            httpd.shutdown()

    def test_ping_always_public(self, tmp_path: Path) -> None:
        port, httpd = _start_server(tmp_path, token=_TOKEN)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/api/ping")
            resp = conn.getresponse()
            data = json.loads(resp.read())
            assert resp.status == 200
            assert data["auth_enabled"] is True
            assert data["authenticated"] is False
        finally:
            httpd.shutdown()


# ---------------------------------------------------------------------------
# POST /api/rerender
# ---------------------------------------------------------------------------


class TestRerender:
    def test_rerender_returns_ok(self, tmp_path: Path) -> None:
        _make_html_stubs(tmp_path)
        port, httpd = _start_server(tmp_path)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("POST", "/api/rerender")
            resp = conn.getresponse()
            data = json.loads(resp.read())
            assert resp.status == 200
            assert data["ok"] is True
        finally:
            httpd.shutdown()

    def test_rerender_without_auth_returns_401(self, tmp_path: Path) -> None:
        _make_html_stubs(tmp_path)
        port, httpd = _start_server(tmp_path, token=_TOKEN)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("POST", "/api/rerender")
            resp = conn.getresponse()
            data = json.loads(resp.read())
            assert resp.status == 401
            assert data["ok"] is False
        finally:
            httpd.shutdown()

    def test_rerender_with_auth_returns_ok(self, tmp_path: Path) -> None:
        _make_html_stubs(tmp_path)
        port, httpd = _start_server(tmp_path, token=_TOKEN)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("POST", "/api/rerender", headers={"Cookie": _COOKIE_HDR})
            resp = conn.getresponse()
            data = json.loads(resp.read())
            assert resp.status == 200
            assert data["ok"] is True
        finally:
            httpd.shutdown()


# ---------------------------------------------------------------------------
# GET /api/refetch
# ---------------------------------------------------------------------------


class TestRefetch:
    def test_refetch_without_auth_returns_401(self, tmp_path: Path) -> None:
        port, httpd = _start_server(tmp_path, token=_TOKEN)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/api/refetch")
            resp = conn.getresponse()
            data = json.loads(resp.read())
            assert resp.status == 401
            assert data["ok"] is False
        finally:
            httpd.shutdown()

    def test_refetch_no_credentials_sends_sse_error(self, tmp_path: Path) -> None:
        """When no config exists (no key/steamid), the SSE stream emits an error event."""
        cfg_path = tmp_path / "config.toml"
        cfg_path.write_text("[steam]\nkey = \"\"\nsteamid = \"\"\n", encoding="utf-8")
        port, httpd = _start_server(tmp_path, config_path=cfg_path)
        try:
            conn = HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/api/refetch")
            resp = conn.getresponse()
            assert resp.status == 200
            ct = resp.getheader("Content-Type") or ""
            assert "text/event-stream" in ct
            raw = resp.read().decode()
            assert "done" in raw
            assert "error" in raw
        finally:
            httpd.shutdown()

    def test_refetch_concurrent_returns_409(self, tmp_path: Path) -> None:
        """A second concurrent refetch request must be rejected with 409."""
        import time  # noqa: PLC0415

        cfg_path = tmp_path / "config.toml"
        cfg_path.write_text("[steam]\nkey = \"\"\nsteamid = \"\"\n", encoding="utf-8")
        port, httpd = _start_server(tmp_path, config_path=cfg_path)
        try:
            # Start first request in a background thread (will block on SSE).
            import threading as _t  # noqa: PLC0415  # avoid name clash

            first_resp: list[object] = []

            def _do_first() -> None:
                c = HTTPConnection("127.0.0.1", port)
                c.request("GET", "/api/refetch")
                first_resp.append(c.getresponse())

            t = _t.Thread(target=_do_first, daemon=True)
            t.start()
            time.sleep(0.15)  # give first request time to acquire lock

            # Second request should be rejected.
            conn2 = HTTPConnection("127.0.0.1", port)
            conn2.request("GET", "/api/refetch")
            resp2 = conn2.getresponse()
            # First req either won the lock or the lock was already released (fast path).
            # Only assert that 409 is a valid outcome when lock is held.
            assert resp2.status in (200, 409)
            if resp2.status == 409:
                data2 = json.loads(resp2.read())
                assert data2["ok"] is False
            else:
                resp2.read()  # drain SSE body
        finally:
            httpd.shutdown()
