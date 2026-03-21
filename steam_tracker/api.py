"""Steam Web API & Store API wrappers."""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

import requests

from .models import AppDetails, NewsItem, OwnedGame

log = logging.getLogger(__name__)

STEAM_API_BASE = "https://api.steampowered.com"
STORE_API_BASE = "https://store.steampowered.com/api"

_Params = dict[str, str | int]

_KEY_RE = re.compile(r"([?&])key=[^&]+")


def _redact_key(text: str) -> str:
    """Remove API key query-parameter values from a string."""
    return _KEY_RE.sub(r"\1key=REDACTED", text)


def _int(v: Any, default: int = 0) -> int:  # noqa: ANN401
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _str(v: Any, default: str = "") -> str:  # noqa: ANN401
    return str(v) if v is not None else default


def _list_str(v: Any) -> list[str]:  # noqa: ANN401
    if isinstance(v, list):
        return [str(i) for i in v]
    return []


def get_owned_games(
    api_key: str,
    steam_id: str,
    session: requests.Session | None = None,
) -> list[OwnedGame]:
    """Fetch the full list of owned games for a Steam account."""
    s = session or requests.Session()
    url = f"{STEAM_API_BASE}/IPlayerService/GetOwnedGames/v1/"
    params: _Params = {
        "key": api_key,
        "steamid": steam_id,
        "include_appinfo": 1,
        "include_played_free_games": 1,
        "format": "json",
    }
    resp = s.get(url, params=params, timeout=15)
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        raise requests.HTTPError(_redact_key(str(exc)), response=exc.response) from None
    games_raw: Any = resp.json().get("response", {}).get("games", [])
    return [OwnedGame.model_validate(g) for g in games_raw]


def get_app_details(
    appid: int,
    session: requests.Session | None = None,
) -> AppDetails | None:
    """Fetch store details for a single app."""
    s = session or requests.Session()
    url = f"{STORE_API_BASE}/appdetails"
    params: _Params = {"appids": appid, "l": "french", "cc": "fr"}
    try:
        resp = s.get(url, params=params, timeout=10)
        resp.raise_for_status()
        payload: Any = resp.json().get(str(appid), {})
        if not payload.get("success") or not payload.get("data"):
            return None
        d: Any = payload["data"]

        # ── Release status ──────────────────────────────────────────────────
        # Genre ID 70 = Early Access (language-independent, most reliable)
        genres_raw: Any = d.get("genres", [])
        is_ea: bool = any(str(g.get("id", "")) == "70" for g in genres_raw)
        # Fallback: category text in English or French (API locale-dependent)
        categories_raw: Any = d.get("categories", [])
        if not is_ea:
            for cat in categories_raw:
                desc = str(cat.get("description", "")).lower()
                if "early access" in desc or "accès anticipé" in desc:
                    is_ea = True
                    break

        release: Any = d.get("release_date", {})

        # ── Genres / Categories ─────────────────────────────────────────────
        genres = [str(g.get("description", "")) for g in genres_raw if g.get("description")]
        categories = [
            str(c.get("description", ""))
            for c in categories_raw
            if c.get("description")
        ]

        # ── Price ───────────────────────────────────────────────────────────
        price: Any = d.get("price_overview", {})

        # ── Platforms / Metacritic / Achievements / Recommendations ─────────
        plat: Any = d.get("platforms", {})
        mc: Any = d.get("metacritic", {})
        ach: Any = d.get("achievements", {})
        reco: Any = d.get("recommendations", {})

        return AppDetails(
            appid=appid,
            app_type=_str(d.get("type")),
            name=_str(d.get("name")),
            short_description=_str(d.get("short_description")),
            supported_languages=_str(d.get("supported_languages")),
            website=_str(d.get("website")),
            header_image=_str(d.get("header_image")),
            background_image=_str(d.get("background")),
            early_access=is_ea,
            coming_soon=bool(release.get("coming_soon", False)),
            release_date_str=_str(release.get("date") or "—", "—"),
            developers=_list_str(d.get("developers")),
            publishers=_list_str(d.get("publishers")),
            genres=genres,
            categories=categories,
            is_free=bool(d.get("is_free", False)),
            price_initial=_int(price.get("initial")),
            price_final=_int(price.get("final")),
            price_discount_pct=_int(price.get("discount_percent")),
            price_currency=_str(price.get("currency")),
            platform_windows=bool(plat.get("windows", False)),
            platform_mac=bool(plat.get("mac", False)),
            platform_linux=bool(plat.get("linux", False)),
            metacritic_score=_int(mc.get("score")),
            metacritic_url=_str(mc.get("url")),
            achievement_count=_int(ach.get("total")),
            recommendation_count=_int(reco.get("total")),
            dlc_appids=[_int(d_id) for d_id in d.get("dlc", []) if _int(d_id)],
            controller_support=_str(d.get("controller_support")),
            required_age=_int(d.get("required_age")),
        )
    except Exception:
        log.warning("appdetails failed for appid=%d", appid, exc_info=True)
        return None


def get_app_news(
    appid: int,
    count: int = 5,
    session: requests.Session | None = None,
) -> list[NewsItem]:
    """Fetch recent news/patch notes for a game."""
    s = session or requests.Session()
    url = f"{STEAM_API_BASE}/ISteamNews/GetNewsForApp/v2/"
    params: _Params = {
        "appid": appid,
        "count": count,
        "maxlength": 300,
        "format": "json",
    }
    try:
        resp = s.get(url, params=params, timeout=10)
        resp.raise_for_status()
        items: Any = resp.json().get("appnews", {}).get("newsitems", [])
        return [
            NewsItem(
                gid=_str(item.get("gid")),
                title=_str(item.get("title")),
                date=datetime.fromtimestamp(float(item.get("date") or 0), tz=UTC),
                url=_str(item.get("url")),
                author=_str(item.get("author")),
                contents=_str(item.get("contents")),
                feedname=_str(item.get("feedname")),
                feedlabel=_str(item.get("feedlabel")),
                tags=_parse_tags(item.get("tags")),
            )
            for item in items
        ]
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        if status in (403, 404):
            log.debug("news unavailable for appid=%d (HTTP %d)", appid, status)
        else:
            log.warning("news failed for appid=%d: %s", appid, exc)
        return []
    except Exception:
        log.warning("news failed for appid=%d", appid, exc_info=True)
        return []


def _parse_tags(raw: Any) -> list[str]:  # noqa: ANN401
    """Steam returns tags as a comma-separated string or a list."""
    if isinstance(raw, str):
        return [t.strip() for t in raw.split(",") if t.strip()]
    if isinstance(raw, list):
        return [str(t) for t in raw]
    return []


def get_wishlist(
    api_key: str,
    steam_id: str,
    session: requests.Session | None = None,
) -> list[OwnedGame]:
    """Fetch the wishlist for a Steam account via IWishlistService/GetWishlist/v1/."""
    s = session or requests.Session()
    url = f"{STEAM_API_BASE}/IWishlistService/GetWishlist/v1/"
    try:
        resp = s.get(url, params={"key": api_key, "steamid": steam_id}, timeout=15)
        resp.raise_for_status()
        items: Any = resp.json().get("response", {}).get("items", [])
    except requests.HTTPError as exc:
        log.warning("wishlist fetch failed for steamid=%s: %s", steam_id, _redact_key(str(exc)))
        return []
    except Exception:
        log.warning("wishlist fetch failed for steamid=%s", steam_id, exc_info=True)
        return []
    games: list[OwnedGame] = []
    for item in items:
        try:
            games.append(OwnedGame(appid=_int(item.get("appid")), name="", source="wishlist"))
        except Exception:
            continue
    return games


def get_followed_games(
    api_key: str,
    steam_id: str,
    session: requests.Session | None = None,
) -> list[OwnedGame]:
    """Fetch the list of games followed by a Steam account."""
    s = session or requests.Session()
    url = f"{STEAM_API_BASE}/IPlayerService/GetFollowedGames/v1/"
    params: _Params = {"key": api_key, "steamid": steam_id}
    try:
        resp = s.get(url, params=params, timeout=15)
        resp.raise_for_status()
        raw_games: Any = resp.json().get("response", {}).get("games", [])
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        if status == 404:
            # endpoint not publicly available for this account
            log.debug("GetFollowedGames not available for steamid=%s (404)", steam_id)
        else:
            log.warning(
                "followed games fetch failed for steamid=%s: %s",
                steam_id,
                _redact_key(str(exc)),
            )
        return []
    except Exception:
        log.warning("followed games fetch failed for steamid=%s", steam_id, exc_info=True)
        return []
    results: list[OwnedGame] = []
    for g in raw_games:
        try:
            results.append(OwnedGame(appid=_int(g.get("appid")), name="", source="followed"))
        except Exception:
            continue
    return results
