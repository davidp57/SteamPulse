"""SteamCMD API wrapper for build and depot information."""

from __future__ import annotations

import logging
from typing import Any

import requests

from .models import SteamCmdInfo

log = logging.getLogger(__name__)

STEAMCMD_API_BASE = "https://api.steamcmd.net/v1"


def _int_safe(v: Any, default: int = 0) -> int:  # noqa: ANN401
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def get_steamcmd_info(
    appid: int,
    session: requests.Session | None = None,
) -> SteamCmdInfo | None:
    """Fetch build and depot information for a single app from the SteamCMD API.

    Retrieves the public branch build ID, last update timestamp, total depot
    size (sum of all numeric depot ``maxsize`` values), and list of branch
    names for the given *appid*.

    Args:
        appid: Steam App ID to query.
        session: Optional :class:`requests.Session` to reuse.  A new session
            is created when ``None``.

    Returns:
        A :class:`~steam_tracker.models.SteamCmdInfo` instance, or ``None``
        when the request fails or the appid is not found.
    """
    s = session or requests.Session()
    url = f"{STEAMCMD_API_BASE}/info/{appid}"
    try:
        resp = s.get(url, params={}, timeout=10)
        resp.raise_for_status()
        payload: Any = resp.json()
        if payload.get("status") != "success":
            log.debug("steamcmd info status!=success for appid=%d", appid)
            return None
        app_data: Any = payload.get("data", {}).get(str(appid))
        if not app_data:
            log.debug("steamcmd no data for appid=%d", appid)
            return None

        depots: Any = app_data.get("depots", {})

        # ── Branch info ────────────────────────────────────────────────────
        branches: Any = depots.get("branches", {})
        public: Any = branches.get("public", {})
        buildid = _int_safe(public.get("buildid"))
        build_timeupdated = _int_safe(public.get("timeupdated"))
        branch_names = list(branches.keys()) if isinstance(branches, dict) else []

        # ── Depot sizes (sum all numeric depot keys) ───────────────────────
        total_size = 0
        for key, depot_info in depots.items():
            if not key.isdigit():
                continue
            if isinstance(depot_info, dict):
                total_size += _int_safe(depot_info.get("maxsize"))

        return SteamCmdInfo(
            appid=appid,
            buildid=buildid,
            build_timeupdated=build_timeupdated,
            depot_size_bytes=total_size,
            branch_names=branch_names,
        )
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        if status in (403, 404):
            log.debug("steamcmd unavailable for appid=%d (HTTP %d)", appid, status)
        else:
            log.warning("steamcmd failed for appid=%d: %s", appid, exc)
        return None
    except Exception:
        log.warning("steamcmd failed for appid=%d", appid, exc_info=True)
        return None
