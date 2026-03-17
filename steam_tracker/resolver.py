"""Resolve game names to Steam AppIDs via multiple sources.

Provides a chain-of-responsibility pattern: each resolver tries to
map a game name to a Steam AppID. The first successful result wins.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from difflib import SequenceMatcher
from typing import Protocol

import requests

log = logging.getLogger(__name__)

# IGDB external_game category enum value for Steam
_IGDB_STEAM_CATEGORY = 1
_SIMILARITY_THRESHOLD = 0.8


class AppIdResolver(Protocol):
    """Protocol for Steam AppID resolvers."""

    def resolve(self, name: str, session: requests.Session | None = None) -> int | None:
        """Resolve a game name to a Steam AppID, or None if not found."""
        ...


def _best_match(target: str, candidates: list[dict[str, object]]) -> dict[str, object] | None:
    """Pick the candidate whose 'name' field is most similar to *target*.

    Returns the best match above the similarity threshold, or None.
    """
    best: dict[str, object] | None = None
    best_ratio = 0.0
    for c in candidates:
        c_name = str(c.get("name", ""))
        ratio = SequenceMatcher(None, target.lower(), c_name.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best = c
    if best_ratio >= _SIMILARITY_THRESHOLD:
        return best
    return None


class SteamStoreResolver:
    """Resolve via the Steam Store search API (zero-config, no auth)."""

    _URL = "https://store.steampowered.com/api/storesearch/"

    def resolve(self, name: str, session: requests.Session | None = None) -> int | None:
        """Search the Steam Store for *name* and return the best matching appid."""
        s = session or requests.Session()
        try:
            resp = s.get(self._URL, params={"term": name, "cc": "us"}, timeout=15)
            resp.raise_for_status()
        except requests.RequestException:
            log.debug("Steam Store search failed for %r", name)
            return None

        items: list[dict[str, object]] = resp.json().get("items", [])
        if not items:
            return None

        match = _best_match(name, items)
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
