"""Minimal i18n: system-language auto-detection with English fallback.

Usage::

    from steam_tracker.i18n import get_translator
    t = get_translator()          # auto-detect
    t = get_translator("fr")      # explicit
    print(t("cli_fetching_library"))
    print(t("cli_owned_count", count=42))

To add a new language, create ``steam_tracker/i18n/<code>.py`` with a
``STRINGS: dict[str, str]`` dictionary (use ``en.py`` as the template).
"""
from __future__ import annotations

import locale
import os
from typing import Any

# Populated lazily on first use
_SUPPORTED: dict[str, dict[str, str]] = {}


def _load_all() -> None:
    from . import en, fr  # noqa: PLC0415

    _SUPPORTED["en"] = en.STRINGS
    _SUPPORTED["fr"] = fr.STRINGS


def detect_lang() -> str:
    """Return a 2-letter language code inferred from the OS environment."""
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var, "")
        if val and val not in ("C", "POSIX"):
            return val[:2].lower()
    try:
        code, _ = locale.getdefaultlocale()  # type: ignore[misc]
        if code:
            return code[:2].lower()
    except Exception:  # noqa: BLE001
        pass
    return "en"


class Translator:
    """Callable that resolves a translation key, falling back to English."""

    def __init__(self, lang: str) -> None:
        if not _SUPPORTED:
            _load_all()
        self._strings = _SUPPORTED.get(lang) or _SUPPORTED["en"]
        self.lang = lang if lang in _SUPPORTED else "en"

    def __call__(self, key: str, **kwargs: Any) -> str:
        s = self._strings.get(key) or _SUPPORTED["en"].get(key, key)
        return s.format(**kwargs) if kwargs else s


def get_translator(lang: str | None = None) -> Translator:
    """Return a :class:`Translator` for *lang* (auto-detect if ``None``)."""
    if not _SUPPORTED:
        _load_all()
    if lang is None:
        lang = detect_lang()
    if lang not in _SUPPORTED:
        lang = "en"
    return Translator(lang)
