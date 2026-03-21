"""TOML configuration file support for SteamPulse.

Config file location:

- Windows: ``%APPDATA%\\steampulse\\config.toml``
- Other:   ``$XDG_CONFIG_HOME/steampulse/config.toml`` (default: ``~/.config``)

The file is read with stdlib ``tomllib`` (Python 3.11+).  Writing is handled
by a simple template-based generator (``tomllib`` is read-only by design).

CLI flags always take precedence over config file values.
"""
from __future__ import annotations

import contextlib
import os
import tomllib
from pathlib import Path
from typing import Any

from steam_tracker.models import AlertRule

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


def write_config(
    data: dict[str, Any],
    path: Path | None = None,
    alert_rules: list[AlertRule] | None = None,
) -> None:
    """Write config data to a TOML file, creating parent directories as needed.

    Only keys that map to known TOML fields are written; unknown/transient
    keys (e.g. ``refresh``, ``verbose``) are silently ignored.

    Args:
        data: Flat dict of argparse ``dest`` → value (same format as
            :func:`load_config`).
        path: Destination path.  Defaults to :func:`get_config_path`.
        alert_rules: Optional list of alert rules to append as ``[[alerts]]``
            entries.  If ``None``, no ``[[alerts]]`` section is written.
    """
    p = path or get_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_build_toml(data, alert_rules), encoding="utf-8")
    print(f"  ✔ Config written to {p}")


def load_alert_rules(path: Path | None = None) -> list[AlertRule]:
    """Load ``[[alerts]]`` entries from the TOML config and inject the builtin rule.

    The builtin "All News" rule (which matches every news item) is always
    prepended so it appears first in the rendered alerts page, regardless of
    TOML ordering.

    Args:
        path: Path to the config file.  Defaults to :func:`get_config_path`.

    Returns:
        A list of :class:`~steam_tracker.models.AlertRule` objects, with the
        builtin "All News" rule first, followed by user-defined rules.
    """
    from steam_tracker.alerts import ALL_NEWS_RULE  # local import avoids circularity

    p = path or get_config_path()
    user_rules: list[AlertRule] = []
    if p.exists():
        with p.open("rb") as f:
            raw = tomllib.load(f)
        for entry in raw.get("alerts", []):
                with contextlib.suppress(Exception):
                    user_rules.append(AlertRule.model_validate(entry))
    return [ALL_NEWS_RULE, *user_rules]


def save_cli_credentials(    args_dict: dict[str, Any],
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
        write_config(updates, path=path)


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


def _build_toml(data: dict[str, Any], alert_rules: list[AlertRule] | None = None) -> str:
    """Build a well-commented TOML string from a flat argparse-key dict.

    Args:
        data: Flat dict of argparse dest → value.
        alert_rules: Optional list of :class:`~steam_tracker.models.AlertRule` objects
            to append as ``[[alerts]]`` array tables.

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
                lines.append(f'{toml_key} = "{_toml_escape(value)}"')
            else:
                lines.append(f"{toml_key} = {value}")
        lines.append("")
    for rule in (alert_rules or []):
        lines.append("[[alerts]]")
        lines.append(f'name = "{_toml_escape(rule.name)}"')
        lines.append(f'rule_type = "{rule.rule_type}"')
        if rule.icon:
            lines.append(f'icon = "{_toml_escape(rule.icon)}"')
        if not rule.enabled:
            lines.append("enabled = false")
        if rule.keywords:
            kws = ", ".join(f'"{_toml_escape(kw)}"' for kw in rule.keywords)
            lines.append(f"keywords = [{kws}]")
        if rule.match and rule.match != "any":
            lines.append(f'match = "{rule.match}"')
        if rule.field:
            lines.append(f'field = "{rule.field}"')
        if rule.condition:
            lines.append(f'condition = "{rule.condition}"')
        lines.append("")
    return "\n".join(lines)


def _toml_escape(value: str) -> str:
    """Escape a string value for embedding in a TOML double-quoted string.

    Handles backslashes, double quotes, and common control characters.

    Args:
        value: Raw string value.

    Returns:
        Escaped string safe for use inside TOML double quotes.
    """
    return (
        value
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
