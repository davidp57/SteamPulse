"""CLI entry points: ``steam-fetch`` and ``steam-render``."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .db import Database
from .fetcher import SteamFetcher
from .i18n import get_translator
from .models import SYNTHETIC_APPID_BASE, OwnedGame
from .renderer import write_html, write_news_html
from .sources import get_all_sources


def _build_enrichment_queue(all_discovered: list[OwnedGame]) -> list[OwnedGame]:
    """Return the deduplicated list of games eligible for Steam Store enrichment.

    Only games with a real Steam AppID (< SYNTHETIC_APPID_BASE) are included.
    Unresolved Epic games carry a hash-based synthetic appid and would always
    receive a 404 from the Steam Store API, so they are excluded.
    The first occurrence of each appid wins (sources yield owned games first).

    Args:
        all_discovered: All games returned by every enabled source.

    Returns:
        Deduplicated list ready to pass to :class:`SteamFetcher`.
    """
    games: list[OwnedGame] = []
    seen: set[int] = set()
    for game in all_discovered:
        if game.appid not in seen and game.appid < SYNTHETIC_APPID_BASE:
            games.append(game)
            seen.add(game.appid)
    return games


def cmd_fetch() -> None:
    """Fetch Steam library data and persist it to a local SQLite database."""
    parser = argparse.ArgumentParser(
        description="Fetch Steam library — store details & news into a local DB",
    )
    parser.add_argument("--key", required=True, help="Steam API key")
    parser.add_argument("--steamid", required=True, help="SteamID64")
    parser.add_argument("--db", default="steam_library.db", help="SQLite DB path")
    parser.add_argument("--max", type=int, default=None, help="Limit to N games (testing)")
    parser.add_argument("--workers", type=int, default=4, help="Thread pool size")
    parser.add_argument(
        "--refresh", action="store_true", help="Re-fetch all, ignoring the local cache"
    )
    parser.add_argument(
        "--news-age",
        type=int,
        default=24,
        metavar="HOURS",
        help="Re-fetch news for games cached more than N hours ago (default: 24)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument(
        "--no-wishlist", action="store_true", help="Ne pas récupérer la wishlist"
    )
    parser.add_argument(
        "--followed", action="store_true",
        help="Récupérer les jeux suivis (non disponible via clé Web API)"
    )
    parser.add_argument("--lang", default=None, help="Language code (e.g. en, fr); default: system")
    args = parser.parse_args()

    t = get_translator(args.lang)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    db = Database(Path(args.db))

    # ── Game discovery (all sources) ───────────────────────────────────────
    all_discovered: list[OwnedGame] = []
    for source in get_all_sources():
        if source.is_enabled(args):
            all_discovered.extend(source.discover_games(args))

    # Upsert everything to DB (DB enforces source priority: owned > wishlist > followed)
    for game in all_discovered:
        db.upsert_game(game)

    games = _build_enrichment_queue(all_discovered)

    if args.max:
        games = games[: args.max]

    skip = set() if args.refresh else db.get_cached_appids()
    stale_news: set[int] | None = (
        None if args.refresh else db.get_stale_news_appids(args.news_age * 3600)
    )
    pending_details = len([g for g in games if g.appid not in skip])
    pending_news = (
        len([g for g in games if g.appid in skip and g.appid in stale_news])
        if stale_news is not None
        else 0
    )
    print(t("cli_pending", details=pending_details, news=pending_news,
            cached=len(skip) - pending_news))
    """Generate the static HTML page from the local database."""
    parser = argparse.ArgumentParser(
        description="Render Steam library HTML from a local DB",
    )
    parser.add_argument("--db", default="steam_library.db", help="SQLite DB path")
    parser.add_argument(
        "--steamid", required=True, help="SteamID64 displayed in the page header"
    )
    parser.add_argument("--output", default="steam_library.html", help="HTML output path")
    parser.add_argument("--lang", default=None, help="Language code (e.g. en, fr); default: system")
    args = parser.parse_args()

    t = get_translator(args.lang)
    db = Database(Path(args.db))
    records = db.get_all_game_records()
    out = Path(args.output)
    news_out = out.parent / "steam_news.html"
    write_html(records, args.steamid, out, news_href=news_out.name, lang=args.lang)
    write_news_html(records, args.steamid, news_out, library_href=out.name, lang=args.lang)
    print(t("cli_render_library", count=len(records), path=out.resolve()))
    print(t("cli_render_news", count=sum(len(r.news) for r in records), path=news_out.resolve()))


def cmd_run() -> None:
    """Fetch Steam library data then immediately render the HTML dashboard."""
    parser = argparse.ArgumentParser(
        description="Fetch Steam library data and render the HTML dashboard in one step",
    )
    parser.add_argument("--db", default="steam_library.db", help="SQLite DB path")
    parser.add_argument("--output", default="steam_library.html", help="HTML output path")
    parser.add_argument("--max", type=int, default=None, help="Limit to N games (testing)")
    parser.add_argument("--workers", type=int, default=4, help="Thread pool size")
    parser.add_argument(
        "--refresh", action="store_true", help="Re-fetch all, ignoring the local cache"
    )
    parser.add_argument(
        "--news-age",
        type=int,
        default=24,
        metavar="HOURS",
        help="Re-fetch news for games cached more than N hours ago (default: 24)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--lang", default=None, help="Language code (e.g. en, fr); default: system")
    for source in get_all_sources():
        source.add_arguments(parser)
    args = parser.parse_args()

    t = get_translator(args.lang)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    db = Database(Path(args.db))

    # ── Game discovery (all sources) ───────────────────────────────────────
    all_discovered: list[OwnedGame] = []
    for source in get_all_sources():
        if source.is_enabled(args):
            all_discovered.extend(source.discover_games(args))

    # Upsert everything to DB (DB enforces source priority: owned > wishlist > followed)
    for game in all_discovered:
        db.upsert_game(game)

    games = _build_enrichment_queue(all_discovered)

    if args.max:
        games = games[: args.max]

    skip = set() if args.refresh else db.get_cached_appids()
    stale_news: set[int] | None = (
        None if args.refresh else db.get_stale_news_appids(args.news_age * 3600)
    )
    pending_details = len([g for g in games if g.appid not in skip])
    pending_news = (
        len([g for g in games if g.appid in skip and g.appid in stale_news])
        if stale_news is not None
        else 0
    )
    print(t("cli_pending", details=pending_details, news=pending_news,
            cached=len(skip) - pending_news))

    width = len(str(pending_details + pending_news)) if (pending_details + pending_news) else 1

    def on_progress(done: int, total: int, name: str) -> None:
        print(f"\r[{done:>{width}}/{total}] {name[:52]:<52}", end="", flush=True)

    fetcher = SteamFetcher(max_workers=args.workers, on_progress=on_progress)
    try:
        results = fetcher.fetch_all(games, skip_appids=skip, refresh_news_appids=stale_news)
    except KeyboardInterrupt:
        print(t("cli_interrupted"))
        return

    failed_details: set[int] = set()
    news_fetched: set[int] = set()
    for appid, (details, news) in results.items():
        if details:
            db.upsert_app_details(details)
        elif appid not in skip:
            failed_details.add(appid)
        db.upsert_news(appid, news)
        news_fetched.add(appid)
    db.mark_fetched(failed_details, details=True)
    db.mark_fetched(news_fetched, news=True)

    print(t("cli_fetch_done", count=len(results), db=args.db))

    # ── Render phase ───────────────────────────────────────────────────────────────────
    print(t("cli_rendering"))
    records = db.get_all_game_records()
    out = Path(args.output)
    news_out = out.parent / "steam_news.html"
    write_html(records, args.steamid, out, news_href=news_out.name, lang=args.lang)
    write_news_html(records, args.steamid, news_out, library_href=out.name, lang=args.lang)
    print(t("cli_render_library", count=len(records), path=out.resolve()))
    print(t("cli_render_news", count=sum(len(r.news) for r in records), path=news_out.resolve()))
