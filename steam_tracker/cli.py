"""CLI entry points: ``steam-fetch``, ``steam-render``, and ``steampulse``."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .config import get_config_path, load_alert_rules, load_config, save_cli_credentials
from .db import Database
from .fetcher import SteamFetcher
from .i18n import get_translator
from .models import (
    SYNTHETIC_APPID_BASE,
    AppDetails,
    DiscoveryStats,
    FieldChange,
    NewsItem,
    OwnedGame,
)
from .renderer import write_alerts_html, write_diagnostic_html, write_html
from .sources import get_all_sources

# ---------------------------------------------------------------------------
# Config / wizard helpers
# ---------------------------------------------------------------------------

# CLI settings flags that are eligible for auto-save to config
_SETTINGS_FLAG_TO_DEST: dict[str, str] = {
    "--db": "db",
    "--workers": "workers",
    "--news-age": "news_age",
    "--lang": "lang",
}


def _has_steam_credentials_in_argv() -> bool:
    """Return True if ``--key`` or ``--steamid`` are present anywhere in sys.argv."""
    return any(
        a == "--key"
        or a.startswith("--key=")
        or a == "--steamid"
        or a.startswith("--steamid=")
        for a in sys.argv[1:]
    )


def _get_explicit_cli_keys() -> set[str]:
    """Return the argparse dest names for settings flags present in sys.argv."""
    explicit: set[str] = set()
    for arg in sys.argv[1:]:
        flag = arg.split("=")[0]
        if flag in _SETTINGS_FLAG_TO_DEST:
            explicit.add(_SETTINGS_FLAG_TO_DEST[flag])
    return explicit


def _pre_parse_config() -> tuple[Path | None, bool]:
    """Extract --config path and --setup flag from sys.argv without consuming args.

    Also normalises the bare subcommand form ``steampulse setup`` to the flag
    form ``steampulse --setup`` so that the main argparse parser does not choke
    on an unrecognised positional argument.

    Returns:
        Tuple of (config_path, setup_requested).
    """
    # Accept 'steampulse setup' as an alias for 'steampulse --setup'
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        sys.argv[1] = "--setup"
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config", default=None)
    pre.add_argument("--setup", action="store_true")
    pre_args, _ = pre.parse_known_args()
    config_path = Path(pre_args.config) if pre_args.config else None
    return config_path, pre_args.setup


def _maybe_run_wizard(
    config: dict[str, object], config_path: Path | None, setup_requested: bool
) -> dict[str, object]:
    """Run the setup wizard when needed, then reload the config.

    Triggers the wizard when:
    - ``--setup`` was explicitly requested, OR
    - The config is empty AND no Steam credentials appear in sys.argv.

    Args:
        config: Previously loaded config dict (may be empty).
        config_path: Explicit config file path (or None for platform default).
        setup_requested: Whether ``--setup`` was explicitly passed.

    Returns:
        Updated config dict (reloaded after the wizard writes the file).
    """
    if setup_requested or (not config and not _has_steam_credentials_in_argv()):
        # Don't interrupt --help / -h with the wizard.
        if "--help" in sys.argv or "-h" in sys.argv:
            return config
        from .wizard import run_wizard

        effective_path = config_path or get_config_path()
        run_wizard(config_path=effective_path)
        # Whether triggered explicitly (--setup) or automatically (no config),
        # always stop here so the user can review the config before the first fetch.
        from .i18n import detect_lang, get_translator

        t = get_translator(detect_lang())
        print(t("cli_wizard_done", path=effective_path))
        sys.exit(0)
    return config


def _require_steam_credentials(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> None:
    """Abort with a friendly error if --key or --steamid are missing.

    Args:
        args: Parsed argument namespace.
        parser: Active ArgumentParser (used to emit the error).
    """
    if not getattr(args, "key", None):
        parser.error(
            "--key is required. Run 'steam-setup' to create a config file,"
            " or pass --key directly."
        )
    if not getattr(args, "steamid", None):
        parser.error(
            "--steamid is required. Run 'steam-setup' to create a config file,"
            " or pass --steamid directly."
        )


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


log = logging.getLogger(__name__)


def _run_cleanup(db: Database, t: object) -> None:
    """Run DB cleanup rules and print a message if any rows were cleaned."""
    cleaned = db.run_cleanup()
    if cleaned:
        print(t("cli_cleanup_done", count=cleaned))  # type: ignore[operator]
    else:
        log.debug("cleanup: nothing to clean")


def _reconcile_removed(
    db: Database,
    pre_active: set[int],
    discovered: list[OwnedGame],
    t: object,
) -> None:
    """Mark newly-missing games as removed and reactivate returned games.

    Args:
        db: Open database instance.
        pre_active: Set of appids that were active before this fetch run.
        discovered: All games discovered during this fetch run.
        t: Translator callable.
    """
    discovered_appids = {g.appid for g in discovered}
    reactivated = db.mark_active(discovered_appids)
    removed = db.mark_removed(pre_active - discovered_appids)
    if reactivated:
        print(t("cli_reactivated_count", count=reactivated))  # type: ignore[operator]
    if removed:
        print(t("cli_removed_count", count=removed))  # type: ignore[operator]


def cmd_fetch() -> None:
    """Fetch Steam library data and persist it to a local SQLite database."""
    config_path, setup_requested = _pre_parse_config()
    config = load_config(config_path)
    config = _maybe_run_wizard(config, config_path, setup_requested)

    parser = argparse.ArgumentParser(
        description="Fetch Steam library — store details & news into a local DB",
    )
    parser.add_argument("--version", action="version", version=f"SteamPulse {__version__}")
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
    parser.add_argument("--lang", default=None, help="Language code (e.g. en, fr); default: system")
    parser.add_argument("--config", default=None, help="Path to config TOML file")
    parser.add_argument(
        "--setup", action="store_true", help="Run the interactive setup wizard and exit"
    )
    for source in get_all_sources():
        source.add_arguments(parser)
    parser.set_defaults(**config)
    args = parser.parse_args()

    _require_steam_credentials(args, parser)

    t = get_translator(args.lang)
    print(t("cli_banner", version=__version__))

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    db = Database(Path(args.db))
    _run_cleanup(db, t)

    from .alerts import AlertEngine  # noqa: PLC0415

    engine = AlertEngine(rules=load_alert_rules(config_path), db=db)

    # ── Game discovery (all sources) ─────────────────────────────────────────
    pre_active_appids = db.get_all_active_appids()
    all_discovered: list[OwnedGame] = []
    for source in get_all_sources():
        if source.is_enabled(args):
            all_discovered.extend(source.discover_games(args, db=db))

    # Persist credentials early so rotated tokens (e.g. Epic refresh_token)
    # survive even if the enrichment phase crashes.
    save_cli_credentials(
        vars(args), existing=config, path=config_path, _explicit_keys=_get_explicit_cli_keys()
    )

    # Upsert everything to DB (DB enforces source priority: owned = epic > wishlist > followed)
    for game in all_discovered:
        db.upsert_game(game)

    # ── Soft-delete reconciliation ─────────────────────────────────────────
    _reconcile_removed(db, pre_active_appids, all_discovered, t)

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
    name_map: dict[int, str] = {g.appid: g.name for g in games}

    def on_progress(done: int, total: int, name: str) -> None:
        print(f"\r[{done:>{width}}/{total}] {name[:52]:<52}", end="", flush=True)

    failed_details: set[int] = set()
    news_fetched: set[int] = set()

    def on_result(appid: int, details: AppDetails | None, news: list[NewsItem]) -> None:
        changes: list[FieldChange] = []
        if details:
            changes = db.upsert_app_details(details)
        elif appid not in skip:
            failed_details.add(appid)
        db.upsert_news(appid, news)
        news_fetched.add(appid)
        game_name = name_map.get(appid, str(appid))
        for alert in engine.evaluate_field_changes(appid, game_name, changes):
            db.upsert_alert(alert)
        for alert in engine.evaluate_news(appid, game_name, news):
            db.upsert_alert(alert)

    fetcher = SteamFetcher(max_workers=args.workers, on_progress=on_progress, on_result=on_result)
    try:
        results = fetcher.fetch_all(games, skip_appids=skip, refresh_news_appids=stale_news)
    except KeyboardInterrupt:
        print(t("cli_interrupted"))
        db.mark_fetched(failed_details, details=True)
        db.mark_fetched(news_fetched, news=True)
        return

    db.mark_fetched(failed_details, details=True)
    db.mark_fetched(news_fetched, news=True)

    print(t("cli_fetch_done", count=len(results), db=args.db))

    n_backfilled = engine.backfill()
    if n_backfilled:
        print(t("cli_backfill_alerts", count=n_backfilled))


def cmd_render() -> None:
    """Generate the static HTML page from the local database."""
    config_path, _ = _pre_parse_config()
    config = load_config(config_path)

    parser = argparse.ArgumentParser(
        description="Render Steam library HTML from a local DB",
    )
    parser.add_argument("--version", action="version", version=f"SteamPulse {__version__}")
    parser.add_argument("--db", default="steam_library.db", help="SQLite DB path")
    parser.add_argument(
        "--steamid",
        required=False,
        default=None,
        help="SteamID64 displayed in the page header (or set via config file)",
    )
    parser.add_argument("--output", default="steam_library.html", help="HTML output path")
    parser.add_argument("--lang", default=None, help="Language code (e.g. en, fr); default: system")
    parser.add_argument("--config", default=None, help="Path to config TOML file")
    parser.set_defaults(**config)
    args = parser.parse_args()

    if not getattr(args, "steamid", None):
        parser.error(
            "--steamid is required. Run 'steam-setup' to create a config file,"
            " or pass --steamid directly."
        )

    t = get_translator(args.lang)
    print(t("cli_banner", version=__version__))
    db = Database(Path(args.db))
    records = db.get_all_game_records()
    out = Path(args.output)
    alerts_out = out.parent / "steam_alerts.html"
    diag_out = out.parent / "steam_diagnostic.html"
    all_alerts = db.get_alerts()
    write_html(
        records, args.steamid, out,
        alerts_href=alerts_out.name, diag_href=diag_out.name, lang=args.lang,
    )
    write_alerts_html(all_alerts, records, args.steamid, alerts_out,
                      library_href=out.name, diag_href=diag_out.name, lang=args.lang)
    unknown_games = [
        r for r in records
        if r.game.appid >= SYNTHETIC_APPID_BASE or r.status.badge == "unknown"
    ]
    write_diagnostic_html(
        db.get_diagnostic_summary(), db.get_all_appid_mappings(), diag_out,
        unknown_games=unknown_games,
        library_href=out.name, alerts_href=alerts_out.name, lang=args.lang,
    )
    print(t("cli_render_library", count=len(records), path=out.resolve()))
    print(t("cli_render_alerts", count=len(all_alerts), path=alerts_out.resolve()))
    print(t("cli_render_diagnostic", path=diag_out.resolve()))


def cmd_run() -> None:
    """Fetch Steam library data then immediately render the HTML dashboard."""
    config_path, setup_requested = _pre_parse_config()
    config = load_config(config_path)
    config = _maybe_run_wizard(config, config_path, setup_requested)

    parser = argparse.ArgumentParser(
        description="Fetch Steam library data and render the HTML dashboard in one step",
    )
    parser.add_argument("--version", action="version", version=f"SteamPulse {__version__}")
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
    parser.add_argument("--config", default=None, help="Path to config TOML file")
    parser.add_argument(
        "--setup", action="store_true", help="Run the interactive setup wizard and exit"
    )
    for source in get_all_sources():
        source.add_arguments(parser)
    parser.set_defaults(**config)
    args = parser.parse_args()

    _require_steam_credentials(args, parser)

    t = get_translator(args.lang)
    print(t("cli_banner", version=__version__))

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    db = Database(Path(args.db))
    _run_cleanup(db, t)
    from .alerts import AlertEngine  # noqa: PLC0415

    engine_run = AlertEngine(rules=load_alert_rules(config_path), db=db)

    # ── Game discovery (all sources) ───────────────────────────────────────
    pre_active_appids_run = db.get_all_active_appids()
    all_discovered: list[OwnedGame] = []
    all_discovery_stats: list[DiscoveryStats] = []
    for source in get_all_sources():
        if source.is_enabled(args):
            all_discovered.extend(source.discover_games(args, db=db))
            stats = getattr(source, "last_stats", None)
            if isinstance(stats, DiscoveryStats):
                all_discovery_stats.append(stats)

    # Persist credentials early so rotated tokens (e.g. Epic refresh_token)
    # survive even if the enrichment phase crashes.
    save_cli_credentials(
        vars(args), existing=config, path=config_path, _explicit_keys=_get_explicit_cli_keys()
    )

    # Upsert everything to DB (DB enforces source priority: owned = epic > wishlist > followed)
    for game in all_discovered:
        db.upsert_game(game)

    # ── Soft-delete reconciliation ───────────────────────────────────────
    _reconcile_removed(db, pre_active_appids_run, all_discovered, t)

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
    name_map_run: dict[int, str] = {g.appid: g.name for g in games}

    def on_progress(done: int, total: int, name: str) -> None:
        print(f"\r[{done:>{width}}/{total}] {name[:52]:<52}", end="", flush=True)

    failed_details: set[int] = set()
    news_fetched: set[int] = set()

    def on_result(appid: int, details: AppDetails | None, news: list[NewsItem]) -> None:
        changes: list[FieldChange] = []
        if details:
            changes = db.upsert_app_details(details)
        elif appid not in skip:
            failed_details.add(appid)
        db.upsert_news(appid, news)
        news_fetched.add(appid)
        game_name = name_map_run.get(appid, str(appid))
        for alert in engine_run.evaluate_field_changes(appid, game_name, changes):
            db.upsert_alert(alert)
        for alert in engine_run.evaluate_news(appid, game_name, news):
            db.upsert_alert(alert)

    fetcher = SteamFetcher(max_workers=args.workers, on_progress=on_progress, on_result=on_result)
    try:
        results = fetcher.fetch_all(games, skip_appids=skip, refresh_news_appids=stale_news)
    except KeyboardInterrupt:
        print(t("cli_interrupted"))
        db.mark_fetched(failed_details, details=True)
        db.mark_fetched(news_fetched, news=True)
        return

    db.mark_fetched(failed_details, details=True)
    db.mark_fetched(news_fetched, news=True)

    print(t("cli_fetch_done", count=len(results), db=args.db))

    n_backfilled = engine_run.backfill()
    if n_backfilled:
        print(t("cli_backfill_alerts", count=n_backfilled))

    # ── Render phase ───────────────────────────────────────────────────────────────────
    print(t("cli_rendering"))
    records = db.get_all_game_records()
    out = Path(args.output)
    alerts_out = out.parent / "steam_alerts.html"
    diag_out = out.parent / "steam_diagnostic.html"
    all_alerts = db.get_alerts()
    write_html(
        records, args.steamid, out,
        alerts_href=alerts_out.name, diag_href=diag_out.name, lang=args.lang,
    )
    write_alerts_html(all_alerts, records, args.steamid, alerts_out,
                      library_href=out.name, diag_href=diag_out.name, lang=args.lang)
    unknown_games = [
        r for r in records
        if r.game.appid >= SYNTHETIC_APPID_BASE or r.status.badge == "unknown"
    ]
    write_diagnostic_html(
        db.get_diagnostic_summary(), db.get_all_appid_mappings(), diag_out,
        discovery_stats=all_discovery_stats,
        unknown_games=unknown_games,
        library_href=out.name, alerts_href=alerts_out.name, lang=args.lang,
    )
    print(t("cli_render_library", count=len(records), path=out.resolve()))
    print(t("cli_render_alerts", count=len(all_alerts), path=alerts_out.resolve()))
    print(t("cli_render_diagnostic", path=diag_out.resolve()))
