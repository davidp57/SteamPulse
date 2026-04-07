"""Tests for steam_tracker.wizard — interactive setup wizard."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from steam_tracker.config import load_config, write_config
from steam_tracker.wizard import run_wizard

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _inputs(*answers: str):  # type: ignore[no-untyped-def]
    """Return a mock input() that yields answers in order, then raises StopIteration."""
    it = iter(answers)
    return lambda _prompt="": next(it)


def _steam_only(
    key: str = "STEAMKEY",
    steamid: str = "76561198001",
    skip_epic: str = "n",
    skip_gog: str = "n",
    enable_gamepass: str = "n",
    skip_twitch: str = "n",
    db: str = "",
    workers: str = "",
    news_age: str = "",
    lang: str = "",
    serve_token: str = "",
    confirm: str = "y",
) -> tuple[str, ...]:
    """Return a standard set of inputs for a Steam-only wizard run."""
    return (
        key, steamid, skip_epic, skip_gog, enable_gamepass, skip_twitch,
        db, workers, news_age, lang, serve_token, confirm,
    )


# ---------------------------------------------------------------------------
# Steam-only flow
# ---------------------------------------------------------------------------


def test_wizard_creates_config_steam_only(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    with patch("builtins.input", _inputs(*_steam_only())):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    assert cfg["key"] == "STEAMKEY"
    assert cfg["steamid"] == "76561198001"


def test_wizard_config_file_is_created(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    with patch("builtins.input", _inputs(*_steam_only())):
        run_wizard(config_path=config_path)
    assert config_path.exists()


def test_wizard_prints_config_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path = tmp_path / "config.toml"
    with patch("builtins.input", _inputs(*_steam_only())):
        run_wizard(config_path=config_path)
    out = capsys.readouterr().out
    assert str(config_path) in out


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


def test_wizard_aborts_on_no_confirmation(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    with patch("builtins.input", _inputs(*_steam_only(confirm="n"))):
        run_wizard(config_path=config_path)
    assert not config_path.exists()


def test_wizard_prints_abort_message(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path = tmp_path / "config.toml"
    with patch("builtins.input", _inputs(*_steam_only(confirm="n"))):
        run_wizard(config_path=config_path)
    out = capsys.readouterr().out
    assert "cancel" in out.lower() or "abort" in out.lower()


# ---------------------------------------------------------------------------
# Custom settings
# ---------------------------------------------------------------------------


def test_wizard_saves_custom_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    with patch("builtins.input", _inputs(*_steam_only(db="my.db", workers="8", lang="fr"))):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    assert cfg["db"] == "my.db"
    assert cfg["workers"] == 8
    assert cfg["lang"] == "fr"


def test_wizard_uses_default_workers_when_empty(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    with patch("builtins.input", _inputs(*_steam_only())):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    # Default workers = 4; empty input = keep default
    assert cfg.get("workers", 4) == 4


def test_wizard_saves_serve_token(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    with patch("builtins.input", _inputs(*_steam_only(serve_token="my-secret-token"))):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    assert cfg["serve_token"] == "my-secret-token"


def test_wizard_no_serve_token_when_empty(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    with patch("builtins.input", _inputs(*_steam_only(serve_token=""))):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    assert "serve_token" not in cfg


def test_wizard_prefills_existing_serve_token(tmp_path: Path) -> None:
    """Pressing Enter on the token prompt keeps the existing token."""
    config_path = tmp_path / "config.toml"
    write_config({"key": "K", "steamid": "S", "serve_token": "OLD-TOKEN"}, path=config_path)
    # All Enter: keep all existing values
    inputs = _inputs("", "", "n", "n", "n", "n", "", "", "", "", "", "")
    with patch("builtins.input", inputs):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    assert cfg["serve_token"] == "OLD-TOKEN"


def test_wizard_summary_masks_serve_token(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The summary must mask serve_token with *** (contains 'token')."""
    config_path = tmp_path / "config.toml"
    with patch("builtins.input", _inputs(*_steam_only(serve_token="topsecret"))):
        run_wizard(config_path=config_path)
    out = capsys.readouterr().out
    assert "serve_token = ***" in out
    assert "topsecret" not in out


# ---------------------------------------------------------------------------
# Twitch / IGDB section
# ---------------------------------------------------------------------------


def test_wizard_saves_twitch_credentials(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    inputs = _inputs(
        "STEAMKEY", "76561198001",            # Steam
        "n",                                  # Skip Epic
        "n",                                  # Skip GOG
        "n",                                  # Disable GamePass
        "y", "TCLIENTID", "TCLIENTSECRET",    # Twitch
        "", "", "", "", "",                    # Default settings
        "y",                                  # Confirm
    )
    with patch("builtins.input", inputs):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    assert cfg["twitch_client_id"] == "TCLIENTID"
    assert cfg["twitch_client_secret"] == "TCLIENTSECRET"


def test_wizard_no_twitch_when_skipped(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    with patch("builtins.input", _inputs(*_steam_only(skip_twitch="n"))):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    assert "twitch_client_id" not in cfg
    assert "twitch_client_secret" not in cfg


# ---------------------------------------------------------------------------
# Epic section
# ---------------------------------------------------------------------------


def test_wizard_saves_epic_refresh_credentials(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    inputs = _inputs(
        "STEAMKEY", "76561198001",   # Steam
        "y",                          # Enable Epic
        "n",                          # Don't open browser automatically
        "AUTHCODE123",                # Paste auth code
        "n",                          # Skip GOG
        "n",                          # Disable GamePass
        "n",                          # Skip Twitch
        "", "", "", "", "",           # Default settings
        "y",                          # Confirm
    )
    mock_token = {"access_token": "tok_abc", "account_id": "ACC123", "refresh_token": "REF_XYZ"}
    with (
        patch("builtins.input", inputs),
        patch("steam_tracker.wizard.epic_auth_with_code", return_value=mock_token),
    ):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    assert cfg["epic_refresh_token"] == "REF_XYZ"
    assert cfg["epic_account_id"] == "ACC123"


def test_wizard_no_epic_when_skipped(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    with patch("builtins.input", _inputs(*_steam_only(skip_epic="n"))):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    assert "epic_refresh_token" not in cfg
    assert "epic_account_id" not in cfg


def test_wizard_epic_auth_failure_continues(tmp_path: Path) -> None:
    """If Epic auth fails, the wizard skips Epic and continues."""
    config_path = tmp_path / "config.toml"
    inputs = _inputs(
        "STEAMKEY", "76561198001",
        "y",
        "n",
        "BADCODE",
        "n",  # Skip GOG
        "n",  # Disable GamePass
        "n",  # Skip Twitch
        "", "", "", "", "",
        "y",
    )
    with (
        patch("builtins.input", inputs),
        patch("steam_tracker.wizard.epic_auth_with_code", side_effect=Exception("auth failed")),
    ):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    # Steam section present despite Epic failure
    assert cfg["key"] == "STEAMKEY"
    assert "epic_refresh_token" not in cfg


def test_wizard_prints_epic_auth_url(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The wizard must print the Epic auth URL for the user to open manually."""
    config_path = tmp_path / "config.toml"
    inputs = _inputs(
        "STEAMKEY", "76561198001",
        "y",
        "n",         # Don't open browser
        "AUTHCODE",
        "n",  # Skip GOG
        "n",  # Disable GamePass
        "n",  # Skip Twitch
        "", "", "", "", "",
        "y",
    )
    mock_token = {"access_token": "tok", "account_id": "A", "refresh_token": "RT"}
    with (
        patch("builtins.input", inputs),
        patch("steam_tracker.wizard.epic_auth_with_code", return_value=mock_token),
    ):
        run_wizard(config_path=config_path)
    out = capsys.readouterr().out
    assert "epicgames.com" in out


def test_wizard_opens_browser_when_requested(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    inputs = _inputs(
        "STEAMKEY", "76561198001",
        "y",
        "y",         # Open browser automatically
        "AUTHCODE",
        "n",  # Skip GOG
        "n",  # Disable GamePass
        "n",  # Skip Twitch
        "", "", "", "", "",
        "y",
    )
    mock_token = {"access_token": "tok", "account_id": "A", "refresh_token": "RT"}
    mock_browser = MagicMock()
    with (
        patch("builtins.input", inputs),
        patch("steam_tracker.wizard.epic_auth_with_code", return_value=mock_token),
        patch("steam_tracker.wizard.webbrowser", mock_browser),
    ):
        run_wizard(config_path=config_path)
    mock_browser.open.assert_called_once()


# ---------------------------------------------------------------------------
# Pre-fill from existing config
# ---------------------------------------------------------------------------


def test_wizard_prefills_steam_credentials(tmp_path: Path) -> None:
    """When existing credentials are present, pressing Enter preserves them."""
    config_path = tmp_path / "config.toml"
    write_config({"key": "OLDKEY", "steamid": "OLDSTEAMID"}, path=config_path)

    # All Enter: keep existing Steam creds, skip Epic/GOG/GamePass/Twitch, keep settings
    inputs = _inputs("", "", "n", "n", "n", "n", "", "", "", "", "", "")
    with patch("builtins.input", inputs):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    assert cfg["key"] == "OLDKEY"
    assert cfg["steamid"] == "OLDSTEAMID"


def test_wizard_shows_hint_when_existing_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A hint about existing values in brackets is shown when config already exists."""
    config_path = tmp_path / "config.toml"
    write_config({"key": "K", "steamid": "S"}, path=config_path)

    inputs = _inputs("", "", "n", "n", "n", "n", "", "", "", "", "", "")
    with patch("builtins.input", inputs):
        run_wizard(config_path=config_path)
    out = capsys.readouterr().out
    assert "existing" in out.lower() or "current" in out.lower()


def test_wizard_keeps_existing_epic_when_no_reauth(tmp_path: Path) -> None:
    """When Epic creds exist and user declines re-auth, existing creds are preserved."""
    config_path = tmp_path / "config.toml"
    write_config(
        {
            "key": "K",
            "steamid": "S",
            "epic_refresh_token": "OLDRT",
            "epic_account_id": "OLDACC",
        },
        path=config_path,
    )
    # Enter x2 (steam), Enter (epic enabled by default), Enter (no reauth by default),
    # n (skip GOG), n (disable GamePass), n (skip twitch), Enter x5 (settings), Enter (confirm)
    inputs = _inputs("", "", "", "", "n", "n", "n", "", "", "", "", "", "")
    with patch("builtins.input", inputs):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    assert cfg["epic_refresh_token"] == "OLDRT"
    assert cfg["epic_account_id"] == "OLDACC"


def test_wizard_prefills_twitch_credentials(tmp_path: Path) -> None:
    """When Twitch creds exist, pressing Enter keeps them; Enable Twitch defaults to yes."""
    config_path = tmp_path / "config.toml"
    write_config(
        {
            "key": "K",
            "steamid": "S",
            "twitch_client_id": "OLDTID",
            "twitch_client_secret": "OLDSEC",
        },
        path=config_path,
    )
    # Enter x2 (steam), n (skip epic), n (skip GOG), n (disable GamePass),
    # Enter (twitch enabled by default), Enter x2 (keep twitch creds),
    # Enter x5 (settings), Enter (confirm)
    inputs = _inputs("", "", "n", "n", "n", "", "", "", "", "", "", "", "", "")
    with patch("builtins.input", inputs):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    assert cfg["twitch_client_id"] == "OLDTID"
    assert cfg["twitch_client_secret"] == "OLDSEC"


def test_wizard_summary_masks_key_secret_and_token(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Summary must print *** for key, twitch_client_secret, and epic_refresh_token."""
    config_path = tmp_path / "config.toml"

    def _fake_epic_auth(code: str) -> dict:  # type: ignore[type-arg]
        return {"refresh_token": "RT_SECRET", "account_id": "ACC123"}

    inputs = _inputs(
        "MYKEY", "MYSTEAMID",
        "y",  # enable Epic
        "n",  # skip opening browser
        "MYAUTHCODE",  # auth code
        "n",  # skip GOG
        "n",  # disable GamePass
        "n",  # skip twitch
        "", "", "", "", "",  # settings defaults
        "y",  # confirm
    )
    with (
        patch("builtins.input", inputs),
        patch("steam_tracker.wizard.epic_auth_with_code", side_effect=_fake_epic_auth),
        patch("steam_tracker.wizard.webbrowser.open"),
    ):
        run_wizard(config_path=config_path)

    captured = capsys.readouterr().out
    assert "key = ***" in captured
    assert "epic_refresh_token = ***" in captured
    assert "RT_SECRET" not in captured
    assert "MYKEY" not in captured


# ---------------------------------------------------------------------------
# GOG section
# ---------------------------------------------------------------------------

# After wizard update the full prompt order is:
# Steam (2), Epic (3: skip/open/code), GOG (2: skip/open/code), GamePass (1),
# Twitch (3: skip/id/secret), Settings (5: db/workers/news_age/lang/serve_token), Confirm


def _with_gog_setup(
    key: str = "STEAMKEY",
    steamid: str = "76561198001",
    gog_auth_code: str = "GOG_CODE",
    skip_twitch: str = "n",
    confirm: str = "y",
) -> tuple[str, ...]:
    """Return inputs for a wizard run that skips Epic, sets up GOG, skips GamePass and Twitch."""
    return (
        key, steamid,  # Steam
        "n",           # Skip Epic
        "y",           # Enable GOG
        "n",           # Don't open browser
        gog_auth_code, # Paste GOG auth code
        "n",           # Skip GamePass
        skip_twitch,   # Skip Twitch
        "", "", "", "", "",  # Default settings
        confirm,
    )


def test_wizard_saves_gog_refresh_credentials(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    mock_token = MagicMock(refresh_token="GOG_RT")
    with (
        patch("builtins.input", _inputs(*_with_gog_setup())),
        patch("steam_tracker.wizard.gog_auth_with_code", return_value=mock_token),
    ):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    assert cfg["gog_refresh_token"] == "GOG_RT"


def test_wizard_no_gog_when_skipped(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    inputs = _inputs(
        "STEAMKEY", "76561198001",  # Steam
        "n",  # Skip Epic
        "n",  # Skip GOG
        "n",  # Skip GamePass
        "n",  # Skip Twitch
        "", "", "", "", "",  # Default settings
        "y",  # Confirm
    )
    with patch("builtins.input", inputs):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    assert "gog_refresh_token" not in cfg


def test_wizard_gog_auth_failure_continues(tmp_path: Path) -> None:
    """If GOG auth fails, the wizard skips GOG and continues."""
    config_path = tmp_path / "config.toml"
    with (
        patch("builtins.input", _inputs(*_with_gog_setup(gog_auth_code="BAD_CODE"))),
        patch(
            "steam_tracker.wizard.gog_auth_with_code",
            side_effect=Exception("auth failed"),
        ),
    ):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    assert cfg["key"] == "STEAMKEY"
    assert "gog_refresh_token" not in cfg


def test_wizard_prints_gog_auth_url(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The wizard must print the GOG auth URL for the user to open manually."""
    config_path = tmp_path / "config.toml"
    mock_token = MagicMock(refresh_token="GOG_RT")
    with (
        patch("builtins.input", _inputs(*_with_gog_setup())),
        patch("steam_tracker.wizard.gog_auth_with_code", return_value=mock_token),
    ):
        run_wizard(config_path=config_path)
    out = capsys.readouterr().out
    assert "gog.com" in out.lower() or "auth.gog" in out.lower()


# ---------------------------------------------------------------------------
# GamePass section
# ---------------------------------------------------------------------------


def test_wizard_saves_gamepass_enabled(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    inputs = _inputs(
        "STEAMKEY", "76561198001",  # Steam
        "n",  # Skip Epic
        "n",  # Skip GOG
        "y",  # Enable GamePass
        "n",  # Skip Twitch
        "", "", "", "", "",  # Default settings
        "y",  # Confirm
    )
    with patch("builtins.input", inputs):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    assert cfg.get("gamepass") is True


def test_wizard_no_gamepass_when_disabled(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    inputs = _inputs(
        "STEAMKEY", "76561198001",
        "n",  # Skip Epic
        "n",  # Skip GOG
        "n",  # Disable GamePass
        "n",  # Skip Twitch
        "", "", "", "", "",
        "y",
    )
    with patch("builtins.input", inputs):
        run_wizard(config_path=config_path)
    cfg = load_config(config_path)
    # gamepass=False or absent means disabled
    assert not cfg.get("gamepass", False)
