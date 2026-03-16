"""TOML configuration file support for SteamPulse.

Config file location:

- Windows: ``%APPDATA%\\steampulse\\config.toml``
- Other:   ``$XDG_CONFIG_HOME/steampulse/config.toml`` (default: ``~/.config``)

The file is read with stdlib ``tomllib`` (Python 3.11+).  Writing is handled
by a simple template-based generator (``tomllib`` is read-only by design).

CLI flags always take precedence over config file values.
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Key mapping  (TOML section, TOML key) → argparse dest
# ---------------------------------------------------------------------------

_TOML_TO_ARGS: dict[tuple[str, str], str] = {
    ("steam", "key"): "key",
    ("steam", "steamid"): "steamid",
    ("epic", "refresh_token"): "epic_refresh_token",
    ("epic", "account_id"): "epic_account_id",
    ("twitch", "client_id"): "twitch_client_id",
    ("twitch", "client_secret"): "twitch_client_secret",
    ("settings", "db"): "db",
    ("settings", "workers"): "workers",
    ("settings", "news_age"): "news_age",
    ("settings", "lang"): "lang",
}

# Reverse mapping for writes
_ARGS_TO_TOML: dict[str, tuple[str, str]] = {v: k for k, v in _TOML_TO_ARGS.items()}

# Keys that represent credentials — always saved when new/changed
_CREDENTIAL_KEYS: frozenset[str] = frozenset({
    "key",
    "steamid",
    "epic_refresh_token",
    "epic_account_id",
    "twitch_client_id",
    "twitch_client_secret",
})

# Keys in [settings] — only saved when explicitly passed on CLI
_SETTINGS_KEYS: frozenset[str] = frozenset({"db", "workers", "news_age", "lang"})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_config_path(_home: Path | None = None) -> Path:
    """Return the platform-appropriate config file path.

    Args:
        _home: Override for ``Path.home()`` (used in tests).

    Returns:
        - Windows: ``%APPDATA%\\steampulse\\config.toml``
        - Other:   ``$XDG_CONFIG_HOME/steampulse/config.toml``
          (defaults to ``~/.config/steampulse/config.toml``)
    """
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            base = Path(appdata)
        else:
            home = _home or Path.home()
            base = home / "AppData" / "Roaming"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg:
            base = Path(xdg)
        else:
            home = _home or Path.home()
            base = home / ".config"
    return base / "steampulse" / "config.toml"


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load the TOML config file and return a flat dict of argparse-ready values.

    Prints the config path when successfully loaded.  Returns ``{}`` silently
    if the file does not exist.

    Args:
        path: Path to the config file.  Defaults to :func:`get_config_path`.

    Returns:
        Dict mapping argparse ``dest`` names to their configured values.

    Raises:
        tomllib.TOMLDecodeError: If the file exists but is not valid TOML.
    """
    p = path or get_config_path()
    if not p.exists():
        return {}
    with p.open("rb") as f:
        raw = tomllib.load(f)
    result: dict[str, Any] = {}
    for (section, key), dest in _TOML_TO_ARGS.items():
        if section in raw and key in raw[section]:
            result[dest] = raw[section][key]
    print(f"  ✔ Config loaded from {p}")
    return result


def write_config(data: dict[str, Any], path: Path | None = None) -> None:
    """Write config data to a TOML file, creating parent directories as needed.

    Only keys that map to known TOML fields are written; unknown/transient
    keys (e.g. ``refresh``, ``verbose``) are silently ignored.

    Args:
        data: Flat dict of argparse ``dest`` → value (same format as
            :func:`load_config`).
        path: Destination path.  Defaults to :func:`get_config_path`.
    """
    p = path or get_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_build_toml(data), encoding="utf-8")
    print(f"  ✔ Config written to {p}")


def save_cli_credentials(
    args_dict: dict[str, Any],
    existing: dict[str, Any],
    path: Path | None = None,
    _explicit_keys: set[str] | None = None,
) -> None:
    """Persist new or changed values from a parsed CLI ``args`` dict.

    Credentials (Steam key, SteamID, Epic creds, Twitch creds) are always
    saved when they are new or changed.  Settings keys (db, workers, …) are
    only saved when they appear in ``_explicit_keys`` (i.e. the caller knows
    they were explicitly passed on the command line, not just argparse defaults).

    Transient flags such as ``refresh``, ``verbose``, and ``max`` are never
    saved regardless of their value.

    Args:
        args_dict: Values from ``vars(args)`` after ``parse_args()``.
        existing: Currently loaded config (from :func:`load_config`).
        path: Config file path.  Defaults to :func:`get_config_path`.
        _explicit_keys: Set of dest names that were explicitly provided on the
            CLI.  ``None`` means all saveable keys are candidates (useful for
            callers that cannot determine explicit keys).
    """
    updates: dict[str, Any] = {**existing}
    changed = False

    for key, val in args_dict.items():
        if val is None:
            continue
        is_credential = key in _CREDENTIAL_KEYS
        is_explicit_setting = key in _SETTINGS_KEYS and (
            _explicit_keys is None or key in _explicit_keys
        )
        if (is_credential or is_explicit_setting) and val != existing.get(key):
            updates[key] = val
            changed = True

    if changed:
        write_config(updates, path)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SECTION_KEYS: list[tuple[str, list[tuple[str, str]]]] = [
    ("steam", [("key", "key"), ("steamid", "steamid")]),
    (
        "epic",
        [
            ("refresh_token", "epic_refresh_token"),
            ("account_id", "epic_account_id"),
        ],
    ),
    ("twitch", [("client_id", "twitch_client_id"), ("client_secret", "twitch_client_secret")]),
    (
        "settings",
        [
            ("db", "db"),
            ("workers", "workers"),
            ("news_age", "news_age"),
            ("lang", "lang"),
        ],
    ),
]


def _build_toml(data: dict[str, Any]) -> str:
    """Build a well-commented TOML string from a flat argparse-key dict.

    Args:
        data: Flat dict of argparse dest → value.

    Returns:
        TOML-formatted string ready to write to disk.
    """
    lines: list[str] = [
        "# SteamPulse configuration file",
        "# Generated by steam-setup — edit manually at any time.",
        "# CLI flags always override values in this file.",
        "",
    ]
    for section_name, pairs in _SECTION_KEYS:
        section_values = [
            (toml_key, data[arg_key])
            for toml_key, arg_key in pairs
            if arg_key in data and data[arg_key] is not None
        ]
        if not section_values:
            continue
        lines.append(f"[{section_name}]")
        for toml_key, value in section_values:
            if isinstance(value, str):
                lines.append(f'{toml_key} = "{value}"')
            else:
                lines.append(f"{toml_key} = {value}")
        lines.append("")
    return "\n".join(lines)
