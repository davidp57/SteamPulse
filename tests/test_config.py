"""Tests for steam_tracker.config — TOML config file support."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path

import pytest

from steam_tracker.config import (
    get_config_path,
    load_alert_rules,
    load_config,
    save_cli_credentials,
    write_config,
)
from steam_tracker.models import AlertRule

# ── get_config_path ───────────────────────────────────────────────────────────


def test_get_config_path_ends_with_config_toml() -> None:
    p = get_config_path()
    assert p.name == "config.toml"
    assert p.parent.name == "steampulse"


def test_get_config_path_windows_uses_appdata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setenv("APPDATA", r"C:\Users\test\AppData\Roaming")
    p = get_config_path()
    assert p == Path(r"C:\Users\test\AppData\Roaming\steampulse\config.toml")


def test_get_config_path_windows_fallback_to_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.delenv("APPDATA", raising=False)
    p = get_config_path(_home=tmp_path)
    assert p == tmp_path / "AppData" / "Roaming" / "steampulse" / "config.toml"


@pytest.mark.skipif(os.name == "nt", reason="PosixPath cannot be instantiated on Windows")
def test_get_config_path_posix_uses_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
    p = get_config_path()
    assert p == Path("/custom/config/steampulse/config.toml")


@pytest.mark.skipif(os.name == "nt", reason="PosixPath cannot be instantiated on Windows")
def test_get_config_path_posix_fallback_to_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    p = get_config_path(_home=tmp_path)
    assert p == tmp_path / ".config" / "steampulse" / "config.toml"


# ── load_config ───────────────────────────────────────────────────────────────


def test_load_config_missing_file_returns_empty_dict(tmp_path: Path) -> None:
    result = load_config(tmp_path / "nonexistent.toml")
    assert result == {}


def test_load_config_steam_section(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('[steam]\nkey = "MYKEY"\nsteamid = "76561198"\n', encoding="utf-8")
    result = load_config(cfg)
    assert result["key"] == "MYKEY"
    assert result["steamid"] == "76561198"


def test_load_config_all_sections(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[steam]\nkey = "K"\nsteamid = "S"\n\n'
        '[epic]\nrefresh_token = "RT"\naccount_id = "AID"\n\n'
        '[twitch]\nclient_id = "TID"\nclient_secret = "TSEC"\n\n'
        '[settings]\ndb = "my.db"\nworkers = 8\nnews_age = 48\nlang = "fr"\n',
        encoding="utf-8",
    )
    result = load_config(cfg)
    assert result["key"] == "K"
    assert result["steamid"] == "S"
    assert result["epic_refresh_token"] == "RT"
    assert result["epic_account_id"] == "AID"
    assert result["twitch_client_id"] == "TID"
    assert result["twitch_client_secret"] == "TSEC"
    assert result["db"] == "my.db"
    assert result["workers"] == 8
    assert result["news_age"] == 48
    assert result["lang"] == "fr"


def test_load_config_invalid_toml_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text("not [ valid toml !!!\n", encoding="utf-8")
    with pytest.raises(tomllib.TOMLDecodeError):
        load_config(cfg)


def test_load_config_prints_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('[steam]\nkey = "K"\n', encoding="utf-8")
    load_config(cfg)
    out = capsys.readouterr().out
    assert str(cfg) in out


def test_load_config_unknown_keys_ignored(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('[steam]\nkey = "K"\nunknown_key = "X"\n', encoding="utf-8")
    result = load_config(cfg)
    assert "unknown_key" not in result
    assert result["key"] == "K"


def test_load_config_partial_section(tmp_path: Path) -> None:
    """Only [steam] section — epic/twitch/settings absent → no error."""
    cfg = tmp_path / "config.toml"
    cfg.write_text('[steam]\nkey = "K"\n', encoding="utf-8")
    result = load_config(cfg)
    assert result == {"key": "K"}


# ── write_config ──────────────────────────────────────────────────────────────


def test_write_config_creates_parent_directory(tmp_path: Path) -> None:
    p = tmp_path / "subdir" / "nested" / "config.toml"
    write_config({"key": "K", "steamid": "S"}, p)
    assert p.exists()


def test_write_config_roundtrip_steam(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    write_config({"key": "MYKEY", "steamid": "76561198"}, p)
    loaded = load_config(p)
    assert loaded["key"] == "MYKEY"
    assert loaded["steamid"] == "76561198"


def test_write_config_roundtrip_all_sections(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    data = {
        "key": "K",
        "steamid": "S",
        "epic_refresh_token": "RT",
        "epic_account_id": "AID",
        "twitch_client_id": "TID",
        "twitch_client_secret": "TSEC",
        "db": "my.db",
        "workers": 8,
        "news_age": 48,
        "lang": "fr",
    }
    write_config(data, p)
    loaded = load_config(p)
    for k, v in data.items():
        assert loaded[k] == v


def test_write_config_prints_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / "config.toml"
    write_config({"key": "K"}, p)
    out = capsys.readouterr().out
    assert str(p) in out


def test_write_config_integer_not_quoted(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    write_config({"workers": 8}, p)
    content = p.read_text(encoding="utf-8")
    assert "workers = 8" in content
    assert '"8"' not in content


def test_write_config_only_writes_known_keys(tmp_path: Path) -> None:
    """Transient/unknown keys in data are silently ignored."""
    p = tmp_path / "config.toml"
    write_config({"key": "K", "refresh": True, "verbose": False}, p)
    loaded = load_config(p)
    assert loaded == {"key": "K"}


# ── save_cli_credentials ──────────────────────────────────────────────────────


def test_save_cli_credentials_saves_new_keys(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    save_cli_credentials({"key": "NEWKEY", "steamid": "1234"}, existing={}, path=p)
    loaded = load_config(p)
    assert loaded["key"] == "NEWKEY"
    assert loaded["steamid"] == "1234"


def test_save_cli_credentials_no_write_if_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "config.toml"
    existing = {"key": "EXISTING", "steamid": "1234"}
    write_config(existing, p)
    capsys.readouterr()  # clear previous output
    save_cli_credentials({"key": "EXISTING", "steamid": "1234"}, existing=existing, path=p)
    # No "Config written" message expected
    assert "written" not in capsys.readouterr().out.lower()


def test_save_cli_credentials_saves_changed_key(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    existing = {"key": "OLD", "steamid": "1234"}
    write_config(existing, p)
    save_cli_credentials({"key": "NEW", "steamid": "1234"}, existing=existing, path=p)
    loaded = load_config(p)
    assert loaded["key"] == "NEW"


def test_save_cli_credentials_preserves_existing_keys(tmp_path: Path) -> None:
    """Keys already in config but absent from args_dict are kept."""
    p = tmp_path / "config.toml"
    existing = {"key": "K", "steamid": "S", "lang": "fr"}
    write_config(existing, p)
    save_cli_credentials({"key": "K"}, existing=existing, path=p)
    loaded = load_config(p)
    assert loaded["lang"] == "fr"


def test_save_cli_credentials_ignores_transient_flags(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    save_cli_credentials(
        {"key": "K", "steamid": "S", "refresh": True, "verbose": True, "max": 10},
        existing={},
        path=p,
    )
    loaded = load_config(p)
    assert "refresh" not in loaded
    assert "verbose" not in loaded
    assert "max" not in loaded


def test_save_cli_credentials_skips_none_values(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    save_cli_credentials({"key": "K", "steamid": None}, existing={}, path=p)
    loaded = load_config(p)
    assert loaded["key"] == "K"
    assert "steamid" not in loaded


def test_save_cli_credentials_saves_settings_if_explicit(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    save_cli_credentials(
        {"key": "K", "steamid": "S", "workers": 8, "lang": "fr"},
        existing={},
        path=p,
        _explicit_keys={"key", "steamid", "workers", "lang"},
    )
    loaded = load_config(p)
    assert loaded["workers"] == 8
    assert loaded["lang"] == "fr"


def test_save_cli_credentials_does_not_save_settings_if_not_explicit(
    tmp_path: Path,
) -> None:
    """Settings keys from argparse defaults (not explicit CLI) are not saved."""
    p = tmp_path / "config.toml"
    save_cli_credentials(
        {"key": "K", "steamid": "S", "workers": 4, "db": "steam_library.db"},
        existing={},
        path=p,
        _explicit_keys={"key", "steamid"},  # workers/db not explicitly passed
    )
    loaded = load_config(p)
    assert "workers" not in loaded
    assert "db" not in loaded


def test_save_cli_credentials_preserves_alert_rules(tmp_path: Path) -> None:
    """Alert rules in config must survive a save_cli_credentials rewrite."""
    p = tmp_path / "config.toml"
    rules = [
        AlertRule(
            name="Price Drop", rule_type="state_change",
            field="price", condition="decreased",
        ),
    ]
    write_config({"key": "K", "steamid": "S"}, p, alert_rules=rules)
    # Verify rules are written
    assert "[[alerts]]" in p.read_text(encoding="utf-8")

    # save_cli_credentials rewrites the config — rules must be preserved
    save_cli_credentials({"key": "NEW"}, existing={"key": "K", "steamid": "S"}, path=p)
    loaded_rules = load_alert_rules(p)
    # First rule is the builtin ALL_NEWS_RULE, second should be the user rule
    assert len(loaded_rules) == 2
    assert loaded_rules[1].name == "Price Drop"
    assert "[[alerts]]" in p.read_text(encoding="utf-8")
