"""Resolve game names to Steam AppIDs via multiple sources.

Provides a chain-of-responsibility pattern: each resolver tries to
map a game name to a Steam AppID. The first successful result wins.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from difflib import SequenceMatcher
from typing import Protocol

import requests

log = logging.getLogger(__name__)

# IGDB external_game category enum value for Steam
_IGDB_STEAM_CATEGORY = 1
_SIMILARITY_THRESHOLD = 0.8

# Word-boundary separators recognised after a prefix match.
_WORD_SEP = re.compile(r"[\s:;\-–—/]")

# Symbols stripped during normalisation (trademarks, copyright).
_SYMBOLS_RE = re.compile(r"[™®©]")

# Non-alphanumeric / non-space chars collapsed to a single space.
_PUNCT_RE = re.compile(r"[^\w\s]+")

# Whitespace collapsed to a single space.
_SPACE_RE = re.compile(r"\s+")

# Common edition / subtitle suffixes stripped before search retry.
_EDITION_SUFFIX_RE = re.compile(
    r"\s*[-–—:]\s*(?:"
    r"(?:game of the year|goty|definitive|ultimate|deluxe|premium|complete|"
    r"gold|enhanced|special|standard|legendary|platinum)\s+edition"
    r"|director'?s?\s+cut"
    r"|remaster(?:ed)?"
    r"|\d+\s+year\s+(?:celebration|anniversary|edition)"
    r")\s*$",
    re.IGNORECASE,
)

# 4-digit year → 2-digit year (e.g. "2022" → "22").
_YEAR_RE = re.compile(r"\b20(\d{2})\b")


class AppIdResolver(Protocol):
    """Protocol for Steam AppID resolvers."""

    def resolve(self, name: str, session: requests.Session | None = None) -> int | None:
        """Resolve a game name to a Steam AppID, or None if not found."""
        ...


def _normalize(text: str) -> str:
    """Lowercase, strip ™®©, collapse punctuation + whitespace."""
    text = _SYMBOLS_RE.sub("", text.lower())
    text = _PUNCT_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip()


def _is_word_contained(target_norm: str, candidate_norm: str) -> bool:
    """Return True if *target_norm* appears at word boundaries inside *candidate_norm*.

    Both arguments must already be normalised (via ``_normalize``).
    """
    idx = candidate_norm.find(target_norm)
    if idx < 0:
        return False
    before_ok = idx == 0 or candidate_norm[idx - 1] == " "
    end = idx + len(target_norm)
    after_ok = end == len(candidate_norm) or candidate_norm[end] == " "
    return before_ok and after_ok


def _is_word_prefix(target: str, candidate: str) -> bool:
    """Return True when *target* is a word-boundary prefix of *candidate*.

    Handles cases like ``"Control"`` → ``"Control Ultimate Edition"``
    or ``"Disco Elysium"`` → ``"Disco Elysium - The Final Cut"``.

    Rejects numbered sequels: ``"Death Stranding"`` will **not** match
    ``"DEATH STRANDING 2: ON THE BEACH"`` because the suffix starts
    with a digit (indicating a different game, not an edition).
    """
    if not candidate.startswith(target):
        return False
    if len(candidate) == len(target):
        return True
    rest = candidate[len(target) :]
    if not _WORD_SEP.match(rest):
        return False
    # Reject sequels: suffix starts with a digit after stripping separators.
    stripped = rest.lstrip(" :;-–—/")
    return not (stripped and stripped[0].isdigit())


def _best_match(target: str, candidates: list[dict[str, object]]) -> dict[str, object] | None:
    """Pick the candidate whose 'name' field is most similar to *target*.

    Uses a three-strategy approach:
    1. Standard SequenceMatcher similarity (threshold 0.8).
    2. Fallback: first word-boundary prefix match in API result order,
       for games whose Steam name contains an edition or subtitle suffix
       (e.g. "Director's Cut", "Ultimate Edition").
    3. Fallback: word-boundary containment — the target appears inside the
       candidate after normalisation (handles missing franchise prefixes
       such as ``"Tom Clancy's"``).
    """
    target_lower = target.lower().strip()
    best: dict[str, object] | None = None
    best_ratio = 0.0

    for c in candidates:
        c_name = str(c.get("name", ""))
        c_lower = c_name.lower().strip()
        ratio = SequenceMatcher(None, target_lower, c_lower).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best = c

    if best_ratio >= _SIMILARITY_THRESHOLD:
        return best

    # Fallback 1: first prefix match in API result order.
    for c in candidates:
        c_name = str(c.get("name", ""))
        c_lower = c_name.lower().strip()
        if _is_word_prefix(target_lower, c_lower):
            return c

    # Fallback 2: first containment match (normalised).
    target_norm = _normalize(target)
    for c in candidates:
        c_name = str(c.get("name", ""))
        c_norm = _normalize(c_name)
        if _is_word_contained(target_norm, c_norm):
            return c

    return None


def _strip_edition(name: str) -> str | None:
    """Remove common edition / subtitle suffixes from *name*.

    Returns the shortened name if it differs from the original, else None.
    Examples::

        "LISA: The Joyful - Definitive Edition"  → "LISA: The Joyful"
        "Rise of the Tomb Raider: 20 Year Celebration" → "Rise of the Tomb Raider"
        "Hades"  → None  (no suffix to strip)
    """
    cleaned = _EDITION_SUFFIX_RE.sub("", name).strip()
    if cleaned and cleaned != name:
        return cleaned
    return None


def _shorten_year(name: str) -> str | None:
    """Replace 4-digit years (20xx) with 2-digit forms.

    Returns the modified name if it differs from the original, else None.
    Example::

        "Farming Simulator 2022" → "Farming Simulator 22"
    """
    shortened = _YEAR_RE.sub(r"\1", name)
    if shortened != name:
        return shortened
    return None


class SteamStoreResolver:
    """Resolve via the Steam Store search API (zero-config, no auth)."""

    _URL = "https://store.steampowered.com/api/storesearch/"

    def resolve(self, name: str, session: requests.Session | None = None) -> int | None:
        """Search the Steam Store for *name* and return the best matching appid.

        If the first search yields no match, retries with a cleaned name
        (edition suffix stripped, or 4-digit year shortened).
        """
        s = session or requests.Session()

        result = self._search(name, s)
        if result is not None:
            return result

        # Retry with edition suffix stripped.
        stripped = _strip_edition(name)
        if stripped:
            result = self._search(stripped, s)
            if result is not None:
                return result

        # Retry with 4-digit year shortened (2022 → 22).
        shortened = _shorten_year(name)
        if shortened:
            result = self._search(shortened, s)
            if result is not None:
                return result

        return None

    def _search(self, term: str, session: requests.Session) -> int | None:
        """Execute a single Steam Store search and return the best match."""
        try:
            resp = session.get(self._URL, params={"term": term, "cc": "us"}, timeout=15)
            resp.raise_for_status()
        except requests.RequestException:
            log.debug("Steam Store search failed for %r", term)
            return None

        items: list[dict[str, object]] = resp.json().get("items", [])
        if not items:
            return None

        match = _best_match(term, items)
        if match is None:
            return None
        try:
            return int(str(match["id"]))
        except (KeyError, TypeError, ValueError):
            return None


class IGDBResolver:
    """Resolve via the IGDB API (requires Twitch client credentials)."""

    _TOKEN_URL = "https://id.twitch.tv/oauth2/token"
    _GAMES_URL = "https://api.igdb.com/v4/games"
    _EXTERNAL_URL = "https://api.igdb.com/v4/external_games"

    def __init__(self, twitch_client_id: str, twitch_client_secret: str) -> None:
        self._client_id = twitch_client_id
        self._client_secret = twitch_client_secret

    def _get_token(self, session: requests.Session) -> str | None:
        """Obtain a Twitch OAuth2 token via client_credentials grant."""
        try:
            resp = session.post(
                self._TOKEN_URL,
                params={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "grant_type": "client_credentials",
                },
                timeout=15,
            )
            resp.raise_for_status()
            return str(resp.json().get("access_token", ""))
        except requests.RequestException:
            log.debug("Twitch OAuth token request failed")
            return None

    def resolve(self, name: str, session: requests.Session | None = None) -> int | None:
        """Search IGDB for *name*, then look up its Steam external_game entry."""
        if not self._client_id or not self._client_secret:
            return None

        s = session or requests.Session()
        token = self._get_token(s)
        if not token:
            return None

        headers = {
            "Client-ID": self._client_id,
            "Authorization": f"Bearer {token}",
        }

        # Step 1: search IGDB games by name
        try:
            resp = s.post(
                self._GAMES_URL,
                headers=headers,
                data=f'search "{name}"; fields name; limit 10;',
                timeout=15,
            )
            resp.raise_for_status()
            games: list[dict[str, object]] = resp.json()
        except requests.RequestException:
            log.debug("IGDB game search failed for %r", name)
            return None

        if not games:
            return None

        # Step 2: pick the best name match
        match = _best_match(name, games)
        if match is None:
            # Fall back to first result if no good fuzzy match
            match = games[0]

        igdb_id = match.get("id")
        if igdb_id is None:
            return None

        # Step 3: look up Steam external_game for this IGDB game
        try:
            resp = s.post(
                self._EXTERNAL_URL,
                headers=headers,
                data=(
                    f"fields uid,category,game;"
                    f" where game = {igdb_id} & category = {_IGDB_STEAM_CATEGORY};"
                    f" limit 1;"
                ),
                timeout=15,
            )
            resp.raise_for_status()
            externals: list[dict[str, object]] = resp.json()
        except requests.RequestException:
            log.debug("IGDB external_games lookup failed for IGDB id %s", igdb_id)
            return None

        if not externals:
            return None

        uid = externals[0].get("uid")
        try:
            return int(str(uid))
        except (TypeError, ValueError):
            return None


def resolve_steam_appid(
    name: str,
    resolvers: Sequence[AppIdResolver],
    session: requests.Session | None = None,
) -> int | None:
    """Try each resolver in order; return the first successful AppID."""
    for resolver in resolvers:
        result = resolver.resolve(name, session)
        if result is not None:
            log.info("Resolved %r → AppID %d via %s", name, result, type(resolver).__name__)
            return result
    log.info("Could not resolve %r to a Steam AppID", name)
    return None
