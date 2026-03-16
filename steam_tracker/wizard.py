"""Interactive setup wizard for SteamPulse configuration.

Guides the user through entering Steam credentials, optional Epic Games and
Twitch/IGDB credentials, and optional settings, then writes a TOML config file.
"""
from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Any

from .config import get_config_path, load_config, write_config
from .epic_api import epic_auth_with_code

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EPIC_AUTH_URL = (
    "https://www.epicgames.com/id/api/redirect"
    "?clientId=34a02cf8f4414e29b15921876da36f9a"
    "&responseType=code"
)

_DEFAULT_WORKERS = 4
_DEFAULT_NEWS_AGE = 24


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ask(prompt: str, default: str | None = None, secret: bool = False) -> str:
    """Prompt the user and return their stripped input.

    If *default* is provided, the existing value is shown in brackets (masked
    when *secret* is ``True``).  Pressing Enter without typing returns the default.

    Args:
        prompt: The prompt text to display.
        default: Pre-filled value from existing config.
        secret: Whether to mask the displayed default with ``***``.

    Returns:
        The user's input, or *default* if they press Enter without input.
    """
    if default is not None:
        display = "***" if secret else default
        full_prompt = f"{prompt} [current: {display}]: "
    else:
        full_prompt = f"{prompt}: "
    answer = input(full_prompt).strip()
    if not answer and default is not None:
        return default
    return answer


def _yes_no(question: str, default_yes: bool = False) -> bool:
    """Ask a yes/no question. Returns True for yes, False for no.

    Args:
        question: The question text (without the [y/N] suffix).
        default_yes: If True, Enter without input means yes (Default: False).

    Returns:
        True if the user answered yes, False otherwise.
    """
    suffix = "[Y/n]" if default_yes else "[y/N]"
    answer = _ask(f"{question} {suffix}: ").lower()
    if not answer:
        return default_yes
    return answer in ("y", "yes")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_wizard(config_path: Path | None = None) -> None:
    """Guide the user interactively through creating a SteamPulse config file.

    Prompts for Steam API credentials, optional Epic Games device credentials
    (including OAuth2 exchange), optional Twitch/IGDB credentials, and optional
    runtime settings.  Displays a summary and writes the config file on confirmation.

    Args:
        config_path: Destination path for the config file.  If ``None``, uses
            the platform default from :func:`~steam_tracker.config.get_config_path`.
    """
    target = config_path or get_config_path()
    existing = load_config(target)

    print()
    print("=" * 60)
    print("  SteamPulse — Setup Wizard")
    print("=" * 60)
    print(f"  Config will be written to: {target}")
    if existing:
        print("  (Existing values shown in brackets — press Enter to keep them)")
    print()

    data: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Step 1 — Steam credentials
    # ------------------------------------------------------------------
    print("[1/4] Steam credentials")
    print("  Steam API key:")
    print("    1. Go to https://steamcommunity.com/dev/apikey")
    print("    2. Log in and enter any domain (e.g. 'localhost')")
    print("    3. Copy the 32-character hexadecimal key shown on the page")
    data["key"] = _ask("  Steam API key", default=existing.get("key"), secret=True)
    print()
    print("  SteamID64:")
    print("    Go to https://steamid.io, enter your Steam username or profile URL,")
    print("    and copy the 17-digit number labelled 'steamID64' (starts with 765).")
    data["steamid"] = _ask("  SteamID64", default=existing.get("steamid"))
    print()

    # ------------------------------------------------------------------
    # Step 2 — Epic Games (optional)
    # ------------------------------------------------------------------
    print("[2/4] Epic Games integration (optional)")
    _epic_keys = ("epic_refresh_token", "epic_account_id")
    _has_epic = all(k in existing for k in _epic_keys)
    if _yes_no("  Enable Epic Games support?", default_yes=_has_epic):
        if _has_epic:
            print("  Epic credentials are already configured.")
            _reauth = _yes_no("  Re-authenticate to replace them?", default_yes=False)
        else:
            _reauth = True
        if _reauth:
            print()
            print("  Epic authentication — how it works:")
            print("    1. Open the URL below in your browser and log in to your Epic account.")
            print("    2. You will be redirected to a JSON page.")
            print('    3. Find the \"authorizationCode\" field and copy its value.')
            print(f"  URL: {_EPIC_AUTH_URL}")
            if _yes_no("  Open URL in browser automatically?", default_yes=True):
                webbrowser.open(_EPIC_AUTH_URL)
            auth_code = _ask("  Paste the authorizationCode value here")
            try:
                token_data = epic_auth_with_code(auth_code)
                data["epic_refresh_token"] = str(token_data["refresh_token"])
                data["epic_account_id"] = str(token_data["account_id"])
                print("  \u2714 Epic credentials obtained successfully.")
            except Exception as exc:  # noqa: BLE001
                print(f"  ✘ Epic authentication failed: {exc}")

                print("  Skipping Epic setup.")
        else:
            # Keep existing Epic credentials as-is
            data["epic_refresh_token"] = existing["epic_refresh_token"]
            data["epic_account_id"] = existing["epic_account_id"]
            print("  ✔ Keeping existing Epic credentials.")
    print()

    # ------------------------------------------------------------------
    # Step 3 — Twitch / IGDB (optional)
    # ------------------------------------------------------------------
    print("[3/4] Twitch/IGDB credentials (optional, for game metadata enrichment)")
    _has_twitch = "twitch_client_id" in existing
    if _yes_no("  Enable Twitch/IGDB integration?", default_yes=_has_twitch):
        print()
        print("  How to get your Twitch credentials:")
        print("    1. Go to https://dev.twitch.tv/console/apps and log in.")
        print("    2. Click 'Register Your Application'.")
        print("       - Name: anything (e.g. 'SteamPulse')")
        print("       - OAuth Redirect URL: http://localhost")
        print("       - Category: Application Integration")
        print("    3. Click 'Create', then open the app and copy the Client ID.")
        print("    4. Click 'New Secret', confirm, then copy the generated Client Secret.")
        data["twitch_client_id"] = _ask(
            "  Twitch Client ID", default=existing.get("twitch_client_id")
        )
        data["twitch_client_secret"] = _ask(
            "  Twitch Client Secret",
            default=existing.get("twitch_client_secret"),
            secret=True,
        )
    print()

    # ------------------------------------------------------------------
    # Step 4 — Settings
    # ------------------------------------------------------------------
    print("[4/4] Settings (press Enter to keep defaults)")
    _def_db = existing.get("db", "steam_library.db")
    db = _ask("  Database path", default=_def_db)
    if db and (db != "steam_library.db" or "db" in existing):
        data["db"] = db
    _def_workers = str(existing.get("workers", _DEFAULT_WORKERS))
    workers_raw = _ask("  Worker threads", default=_def_workers)
    if workers_raw and (workers_raw != str(_DEFAULT_WORKERS) or "workers" in existing):
        data["workers"] = int(workers_raw)
    _def_news_age = str(existing.get("news_age", _DEFAULT_NEWS_AGE))
    news_age_raw = _ask("  News age (hours)", default=_def_news_age)
    if news_age_raw and (news_age_raw != str(_DEFAULT_NEWS_AGE) or "news_age" in existing):
        data["news_age"] = int(news_age_raw)
    _def_lang = existing.get("lang")
    lang = _ask("  Language (en/fr)     [auto]", default=_def_lang)
    if lang:
        data["lang"] = lang
    print()

    # ------------------------------------------------------------------
    # Summary + confirmation
    # ------------------------------------------------------------------
    _sensitive = frozenset({"key"})
    print("Summary:")
    for k, v in data.items():
        masked = k in _sensitive or any(word in k for word in ("secret", "token"))
        display = "***" if masked else str(v)
        print(f"  {k} = {display}")
    print()

    if not _yes_no("Write config file?", default_yes=True):
        print("Cancelled. No file was written.")
        return

    write_config(data, path=target)
