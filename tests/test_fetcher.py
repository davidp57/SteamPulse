"""Tests for steam_tracker.fetcher."""
from __future__ import annotations

import threading
import time
from unittest.mock import patch

from steam_tracker.fetcher import RateLimiter, SteamFetcher
from steam_tracker.models import OwnedGame


def test_rate_limiter_first_call_has_no_delay() -> None:
    limiter = RateLimiter(0.5)
    t0 = time.monotonic()
    limiter.acquire()
    assert time.monotonic() - t0 < 0.1


def test_rate_limiter_second_call_is_delayed() -> None:
    limiter = RateLimiter(0.1)
    limiter.acquire()
    t0 = time.monotonic()
    limiter.acquire()
    assert time.monotonic() - t0 >= 0.08  # allow slight timing tolerance


def test_rate_limiter_is_thread_safe() -> None:
    limiter = RateLimiter(0.05)
    timestamps: list[float] = []
    lock = threading.Lock()

    def worker() -> None:
        limiter.acquire()
        with lock:
            timestamps.append(time.monotonic())

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    timestamps.sort()
    for i in range(1, len(timestamps)):
        assert timestamps[i] - timestamps[i - 1] >= 0.04


def test_fetcher_skips_cached_appids() -> None:
    games = [OwnedGame(appid=1, name="A"), OwnedGame(appid=2, name="B")]
    fetcher = SteamFetcher(rate_limit=0.0, max_workers=1)

    with patch.object(fetcher, "_fetch_one", return_value=(1, None, [])) as mock:
        results = fetcher.fetch_all(games, skip_appids={2})

    assert mock.call_count == 1
    assert 2 not in results
    assert 1 in results


def test_fetcher_returns_none_on_exception() -> None:
    games = [OwnedGame(appid=42, name="Broken")]
    fetcher = SteamFetcher(rate_limit=0.0, max_workers=1)

    with patch.object(fetcher, "_fetch_one", side_effect=RuntimeError("boom")):
        results = fetcher.fetch_all(games)

    details, news = results[42]
    assert details is None
    assert news == []


def test_fetcher_calls_on_progress_for_each_game() -> None:
    games = [OwnedGame(appid=1, name="A"), OwnedGame(appid=2, name="B")]
    calls: list[tuple[int, int, str]] = []
    fetcher = SteamFetcher(
        rate_limit=0.0,
        max_workers=2,
        on_progress=lambda done, total, name: calls.append((done, total, name)),
    )

    with patch.object(fetcher, "_fetch_one", side_effect=lambda g, s: (g.appid, None, [])):
        fetcher.fetch_all(games)

    assert len(calls) == 2
    assert all(total == 2 for _, total, _ in calls)


def test_fetcher_returns_empty_dict_when_all_skipped() -> None:
    games = [OwnedGame(appid=1, name="A")]
    fetcher = SteamFetcher(rate_limit=0.0, max_workers=1)
    results = fetcher.fetch_all(games, skip_appids={1})
    assert results == {}
