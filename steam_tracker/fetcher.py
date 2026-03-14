"""Multi-threaded Steam data fetcher with thread-safe rate limiting."""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed

import requests

from .api import get_app_details, get_app_news
from .models import AppDetails, NewsItem, OwnedGame

log = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]
FetchResult = dict[int, tuple[AppDetails | None, list[NewsItem]]]


class RateLimiter:
    """Thread-safe rate limiter that enforces a minimum interval between calls."""

    def __init__(self, min_interval: float) -> None:
        self._min_interval = min_interval
        self._lock = threading.Lock()
        self._last_call: float = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()


class SteamFetcher:
    """Fetch app details and news for a list of games using a thread pool.

    The *appdetails* Steam Store endpoint allows ~200 req/5 min per IP.
    A shared :class:`RateLimiter` serialises those calls across threads while
    still allowing overlapping network I/O for news calls.
    """

    def __init__(
        self,
        rate_limit: float = 1.5,
        max_workers: int = 4,
        news_per_game: int = 5,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        self._limiter = RateLimiter(rate_limit)
        self._max_workers = max_workers
        self._news_per_game = news_per_game
        self._on_progress: ProgressCallback = on_progress or (lambda *_: None)

    def _fetch_one(
        self,
        game: OwnedGame,
        session: requests.Session,
        *,
        fetch_details: bool = True,
    ) -> tuple[int, AppDetails | None, list[NewsItem]]:
        details: AppDetails | None = None
        if fetch_details:
            self._limiter.acquire()
            details = get_app_details(game.appid, session=session)
        news = get_app_news(game.appid, count=self._news_per_game, session=session)
        return game.appid, details, news

    def fetch_all(
        self,
        games: list[OwnedGame],
        skip_appids: set[int] | None = None,
        refresh_news_appids: set[int] | None = None,
    ) -> FetchResult:
        """Fetch details + news for every game not in *skip_appids*.

        Games in *skip_appids* are normally skipped entirely.  If
        *refresh_news_appids* is provided, those games (even if cached) will
        have their news re-fetched without re-fetching app details.

        Returns a mapping ``{appid: (details, news)}``.
        """
        skip = skip_appids or set()
        to_fetch_full = [g for g in games if g.appid not in skip]
        to_fetch_news = (
            [g for g in games if g.appid in skip and g.appid in refresh_news_appids]
            if refresh_news_appids is not None
            else []
        )
        all_to_fetch = to_fetch_full + to_fetch_news
        results: FetchResult = {}

        if not all_to_fetch:
            return results

        sessions = [requests.Session() for _ in range(self._max_workers)]
        done = 0
        total = len(all_to_fetch)

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            _future_t = Future[tuple[int, AppDetails | None, list[NewsItem]]]
            future_to_game: dict[_future_t, OwnedGame] = {
                pool.submit(self._fetch_one, game, sessions[idx % self._max_workers]): game
                for idx, game in enumerate(to_fetch_full)
            }
            offset = len(to_fetch_full)
            for idx, game in enumerate(to_fetch_news):
                future_to_game[
                    pool.submit(
                        self._fetch_one,
                        game,
                        sessions[(offset + idx) % self._max_workers],
                        fetch_details=False,
                    )
                ] = game

            try:
                for fut in as_completed(future_to_game):
                    game = future_to_game[fut]
                    done += 1
                    try:
                        appid, details, news = fut.result()
                        results[appid] = (details, news)
                    except Exception:
                        log.error(
                            "fetch failed for %s (%d)", game.name, game.appid, exc_info=True
                        )
                        results[game.appid] = (None, [])
                    self._on_progress(done, total, game.name)
            except KeyboardInterrupt:
                print("\n⚠ Interruption — annulation des tâches en cours...")
                for f in future_to_game:
                    f.cancel()
                pool.shutdown(wait=False, cancel_futures=True)
                raise

        for s in sessions:
            s.close()

        return results
