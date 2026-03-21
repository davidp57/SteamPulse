"""Tests for steam_tracker.steamcmd_api."""
from __future__ import annotations

import responses as resp_mock

from steam_tracker.models import SteamCmdInfo
from steam_tracker.steamcmd_api import STEAMCMD_API_BASE, get_steamcmd_info

_APPID = 420

# Minimal SteamCMD response fixture
_STEAMCMD_RESPONSE = {
    "status": "success",
    "data": {
        str(_APPID): {
            "appid": str(_APPID),
            "common": {"name": "Half-Life 2"},
            "depots": {
                "branches": {
                    "public": {
                        "buildid": "12345678",
                        "timeupdated": "1700000000",
                    },
                    "beta": {
                        "buildid": "12345679",
                        "timeupdated": "1700000001",
                    },
                },
                "1": {"maxsize": "500000000"},
                "2": {"maxsize": "300000000"},
                "oslist": "windows",  # non-numeric key, should be ignored
            },
        }
    },
}


@resp_mock.activate
def test_get_steamcmd_info_returns_steamcmdinfo() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{STEAMCMD_API_BASE}/info/{_APPID}",
        json=_STEAMCMD_RESPONSE,
    )
    result = get_steamcmd_info(_APPID)
    assert isinstance(result, SteamCmdInfo)
    assert result.appid == _APPID


@resp_mock.activate
def test_get_steamcmd_info_parses_buildid() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{STEAMCMD_API_BASE}/info/{_APPID}",
        json=_STEAMCMD_RESPONSE,
    )
    result = get_steamcmd_info(_APPID)
    assert result is not None
    assert result.buildid == 12345678


@resp_mock.activate
def test_get_steamcmd_info_parses_build_timeupdated() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{STEAMCMD_API_BASE}/info/{_APPID}",
        json=_STEAMCMD_RESPONSE,
    )
    result = get_steamcmd_info(_APPID)
    assert result is not None
    assert result.build_timeupdated == 1700000000


@resp_mock.activate
def test_get_steamcmd_info_sums_depot_sizes() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{STEAMCMD_API_BASE}/info/{_APPID}",
        json=_STEAMCMD_RESPONSE,
    )
    result = get_steamcmd_info(_APPID)
    assert result is not None
    assert result.depot_size_bytes == 800000000  # 500M + 300M


@resp_mock.activate
def test_get_steamcmd_info_collects_branch_names() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{STEAMCMD_API_BASE}/info/{_APPID}",
        json=_STEAMCMD_RESPONSE,
    )
    result = get_steamcmd_info(_APPID)
    assert result is not None
    assert set(result.branch_names) == {"public", "beta"}


@resp_mock.activate
def test_get_steamcmd_info_returns_none_on_404() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{STEAMCMD_API_BASE}/info/{_APPID}",
        status=404,
    )
    assert get_steamcmd_info(_APPID) is None


@resp_mock.activate
def test_get_steamcmd_info_returns_none_on_failed_status() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{STEAMCMD_API_BASE}/info/{_APPID}",
        json={"status": "error", "data": {}},
    )
    assert get_steamcmd_info(_APPID) is None


@resp_mock.activate
def test_get_steamcmd_info_returns_none_when_appid_missing() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{STEAMCMD_API_BASE}/info/{_APPID}",
        json={"status": "success", "data": {}},
    )
    assert get_steamcmd_info(_APPID) is None


@resp_mock.activate
def test_get_steamcmd_info_missing_branches_defaults() -> None:
    """A response with no depots/branches should still return a valid object with defaults."""
    resp_mock.add(
        resp_mock.GET,
        f"{STEAMCMD_API_BASE}/info/{_APPID}",
        json={
            "status": "success",
            "data": {
                str(_APPID): {
                    "appid": str(_APPID),
                    "depots": {},
                }
            },
        },
    )
    result = get_steamcmd_info(_APPID)
    assert result is not None
    assert result.buildid == 0
    assert result.branch_names == []
    assert result.depot_size_bytes == 0
