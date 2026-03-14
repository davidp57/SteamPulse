"""CLI entry points: ``steam-fetch`` and ``steam-render``."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .api import get_followed_games, get_owned_games, get_wishlist
from .db import Database
from .fetcher import SteamFetcher
from .renderer import write_html, write_news_html


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
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    db = Database(Path(args.db))

    # ── Jeux possédés ─────────────────────────────────────────────────────────────────────
    print("📦 Récupération de la bibliothèque Steam...")
    owned = get_owned_games(args.key, args.steamid)
    if args.max:
        owned = owned[: args.max]
    print(f"   ✅ {len(owned)} jeu(x) possédé(s)")
    for game in owned:
        db.upsert_game(game)
    games = list(owned)
    seen: set[int] = {g.appid for g in games}

    # ── Wishlist ─────────────────────────────────────────────────────────────────────
    if not args.no_wishlist:
        print("🎁 Récupération de la wishlist...")
        try:
            wishlist = get_wishlist(args.key, args.steamid)
            new_wl = [g for g in wishlist if g.appid not in seen]
            for g in wishlist:
                db.upsert_game(g)
            games += new_wl
            seen.update(g.appid for g in new_wl)
            print(f"   ✅ {len(wishlist)} jeu(x) en wishlist · {len(new_wl)} nouveau(x)")
        except Exception as exc:  # noqa: BLE001
            print(f"   ⚠ Wishlist inaccessible ({exc})")

    # ── Jeux suivis ────────────────────────────────────────────────────────────────────
    if args.followed:
        print("👁 Récupération des jeux suivis...")
        try:
            followed = get_followed_games(args.key, args.steamid)
            new_fol = [g for g in followed if g.appid not in seen]
            for g in followed:
                db.upsert_game(g)
            games += new_fol
            seen.update(g.appid for g in new_fol)
            print(f"   ✅ {len(followed)} jeu(x) suivi(s) · {len(new_fol)} nouveau(x)")
        except Exception as exc:  # noqa: BLE001
            print(f"   ⚠ Jeux suivis inaccessibles ({exc})")

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
    print(
        f"   {pending_details} jeu(x) à récupérer · {pending_news} news à rafraîchir"
        f" ({len(skip) - pending_news} déjà à jour)"
    )

    width = len(str(pending_details + pending_news)) if (pending_details + pending_news) else 1

    def on_progress(done: int, total: int, name: str) -> None:
        print(f"\r[{done:>{width}}/{total}] {name[:52]:<52}", end="", flush=True)

    fetcher = SteamFetcher(max_workers=args.workers, on_progress=on_progress)
    try:
        results = fetcher.fetch_all(games, skip_appids=skip, refresh_news_appids=stale_news)
    except KeyboardInterrupt:
        print("\nArrêt.")
        return

    for appid, (details, news) in results.items():
        if details:
            db.upsert_app_details(details)
        db.upsert_news(appid, news)

    print(f"\n✅ Done — {len(results)} entrée(s) mise(s) à jour dans {args.db}")


def cmd_render() -> None:
    """Generate the static HTML page from the local database."""
    parser = argparse.ArgumentParser(
        description="Render Steam library HTML from a local DB",
    )
    parser.add_argument("--db", default="steam_library.db", help="SQLite DB path")
    parser.add_argument(
        "--steamid", required=True, help="SteamID64 displayed in the page header"
    )
    parser.add_argument("--output", default="steam_library.html", help="HTML output path")
    args = parser.parse_args()

    db = Database(Path(args.db))
    records = db.get_all_game_records()
    out = Path(args.output)
    news_out = out.parent / "steam_news.html"
    write_html(records, args.steamid, out, news_href=news_out.name)
    write_news_html(records, args.steamid, news_out, library_href=out.name)
    print(f"\u2705 {len(records)} jeux · biblioth\u00e8que \u2192 {out.resolve()}")
    print(f"   {sum(len(r.news) for r in records)} news \u2192 {news_out.resolve()}")


def cmd_run() -> None:
    """Fetch Steam library data then immediately render the HTML dashboard."""
    parser = argparse.ArgumentParser(
        description="Fetch Steam library data and render the HTML dashboard in one step",
    )
    parser.add_argument("--key", required=True, help="Steam API key")
    parser.add_argument("--steamid", required=True, help="SteamID64")
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
    parser.add_argument(
        "--no-wishlist", action="store_true", help="Ne pas récupérer la wishlist"
    )
    parser.add_argument(
        "--followed", action="store_true",
        help="Récupérer les jeux suivis (non disponible via clé Web API)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    db = Database(Path(args.db))

    # ── Fetch phase ────────────────────────────────────────────────────────────────────
    print("📦 Récupération de la bibliothèque Steam...")
    owned = get_owned_games(args.key, args.steamid)
    if args.max:
        owned = owned[: args.max]
    print(f"   ✅ {len(owned)} jeu(x) possédé(s)")
    for game in owned:
        db.upsert_game(game)
    games = list(owned)
    seen: set[int] = {g.appid for g in games}

    if not args.no_wishlist:
        print("🎁 Récupération de la wishlist...")
        try:
            wishlist = get_wishlist(args.key, args.steamid)
            new_wl = [g for g in wishlist if g.appid not in seen]
            for g in wishlist:
                db.upsert_game(g)
            games += new_wl
            seen.update(g.appid for g in new_wl)
            print(f"   ✅ {len(wishlist)} jeu(x) en wishlist · {len(new_wl)} nouveau(x)")
        except Exception as exc:  # noqa: BLE001
            print(f"   ⚠ Wishlist inaccessible ({exc})")

    if args.followed:
        print("👁 Récupération des jeux suivis...")
        try:
            followed = get_followed_games(args.key, args.steamid)
            new_fol = [g for g in followed if g.appid not in seen]
            for g in followed:
                db.upsert_game(g)
            games += new_fol
            seen.update(g.appid for g in new_fol)
            print(f"   ✅ {len(followed)} jeu(x) suivi(s) · {len(new_fol)} nouveau(x)")
        except Exception as exc:  # noqa: BLE001
            print(f"   ⚠ Jeux suivis inaccessibles ({exc})")

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
    print(
        f"   {pending_details} jeu(x) à récupérer · {pending_news} news à rafraîchir"
        f" ({len(skip) - pending_news} déjà à jour)"
    )

    width = len(str(pending_details + pending_news)) if (pending_details + pending_news) else 1

    def on_progress(done: int, total: int, name: str) -> None:
        print(f"\r[{done:>{width}}/{total}] {name[:52]:<52}", end="", flush=True)

    fetcher = SteamFetcher(max_workers=args.workers, on_progress=on_progress)
    try:
        results = fetcher.fetch_all(games, skip_appids=skip, refresh_news_appids=stale_news)
    except KeyboardInterrupt:
        print("\nArrêt.")
        return

    for appid, (details, news) in results.items():
        if details:
            db.upsert_app_details(details)
        db.upsert_news(appid, news)

    print(f"\n✅ Fetch terminé — {len(results)} entrée(s) mise(s) à jour dans {args.db}")

    # ── Render phase ───────────────────────────────────────────────────────────────────
    print("🖥  Génération des pages HTML...")
    records = db.get_all_game_records()
    out = Path(args.output)
    news_out = out.parent / "steam_news.html"
    write_html(records, args.steamid, out, news_href=news_out.name)
    write_news_html(records, args.steamid, news_out, library_href=out.name)
    print(f"✅ {len(records)} jeux · bibliothèque → {out.resolve()}")
    print(f"   {sum(len(r.news) for r in records)} news → {news_out.resolve()}")
