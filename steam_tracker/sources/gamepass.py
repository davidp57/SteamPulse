"""Xbox Game Pass source plugin.

Discovers games from the Microsoft PC Game Pass catalog using Microsoft's
public catalog APIs — no authentication is required.  Each game is resolved
to a Steam AppID when possible; unresolved games receive a deterministic
hash-based synthetic AppID.
"""

from __future__ import annotations

import argparse
import logging
from typing import TYPE_CHECKING

from ..gamepass_api import gamepass_get_catalog_ids, gamepass_get_titles
from ..i18n import get_translator
from ..models import DiscoveryStats, OwnedGame, SkippedItem, hash_synthetic_appid
from ..resolver import IGDBResolver, SteamStoreResolver, resolve_steam_appid

if TYPE_CHECKING:
    from ..db import Database

log = logging.getLogger(__name__)


class GamePassSource:
    """Game source plugin for Xbox Game Pass (PC).

    Fetches the public PC Game Pass catalog from Microsoft's endpoints and
    resolves each title to a Steam AppID via the resolver chain.
    """

    name = "gamepass"
    source_labels: frozenset[str] = frozenset({"gamepass"})
    last_stats: DiscoveryStats | None = None

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Register Game Pass CLI flag.

        Args:
            parser: The argument parser to extend.
        """
        parser.add_argument(
            "--game-pass",
            dest="gamepass",
            action="store_true",
            default=False,
            help="Include Xbox PC Game Pass titles in the library",
        )

    def is_enabled(self, args: argparse.Namespace) -> bool:
        """Return True when the ``--game-pass`` flag is set.

        Args:
            args: Parsed CLI namespace.

        Returns:
            True if ``args.gamepass`` is True.
        """
        return bool(getattr(args, "gamepass", False))

    def discover_games(
        self, args: argparse.Namespace, db: Database | None = None
    ) -> list[OwnedGame]:
        """Discover PC Game Pass titles and resolve Steam AppIDs.

        Args:
            args: Parsed CLI namespace.
            db: Optional database instance used to cache name→AppID resolutions.

        Returns:
            List of discovered games with source="gamepass".

        Raises:
            Exception: Re-raises API errors after printing a diagnostic message.
        """
        t = get_translator(getattr(args, "lang", None))

        # ── Fetch catalog IDs ──────────────────────────────────────────
        try:
            store_ids = gamepass_get_catalog_ids()
        except Exception as exc:  # noqa: BLE001
            print(t("cli_gamepass_catalog_error", error=exc))
            raise

        print(t("cli_gamepass_catalog_count", count=len(store_ids)))

        if not store_ids:
            self.last_stats = DiscoveryStats(
                source="gamepass",
                total_api_items=0,
                accepted_count=0,
                resolved_count=0,
                unresolved_count=0,
                skipped_items=[],
            )
            return []

        # ── Fetch titles ───────────────────────────────────────────────
        try:
            titles: dict[str, str] = gamepass_get_titles(store_ids)
        except Exception as exc:  # noqa: BLE001
            print(t("cli_gamepass_titles_error", error=exc))
            raise

        print(t("cli_gamepass_titles_count", count=len(titles)))

        # ── Build resolver chain ───────────────────────────────────────
        resolvers: list[SteamStoreResolver | IGDBResolver] = [SteamStoreResolver()]
        twitch_id = getattr(args, "twitch_client_id", None)
        twitch_secret = getattr(args, "twitch_client_secret", None)
        if twitch_id and twitch_secret:
            resolvers.append(IGDBResolver(str(twitch_id), str(twitch_secret)))

        # ── Resolve each game ──────────────────────────────────────────
        print(t("cli_gamepass_resolving"))
        games: list[OwnedGame] = []
        resolved_count = 0
        skipped: list[SkippedItem] = []
        total = len(store_ids)
        width = len(str(total))

        for idx, store_id in enumerate(store_ids, 1):
            name = titles.get(store_id, "").strip()
            if not name:
                skipped.append(SkippedItem(catalog_id=store_id, raw_name="", reason="no_title"))
                continue

            print(f"\r   [{idx:>{width}}/{total}] {name[:55]:<55}", end="", flush=True)

            external_id = f"gamepass:{store_id}"
            steam_appid: int | None = None
            if db is not None:
                steam_appid = db.get_appid_mapping("gamepass", external_id)
            if steam_appid is None:
                steam_appid = resolve_steam_appid(name, resolvers)
                if db is not None:
                    db.upsert_appid_mapping("gamepass", external_id, name, steam_appid)

            appid = steam_appid if steam_appid is not None else hash_synthetic_appid(store_id)
            if steam_appid is not None:
                resolved_count += 1

            games.append(
                OwnedGame(
                    appid=appid,
                    name=name,
                    source="gamepass",
                    external_id=external_id,
                )
            )

        print()  # newline after the progress line
        print(
            t(
                "cli_gamepass_resolved_done",
                resolved=resolved_count,
                total=len(games),
                unresolved=len(games) - resolved_count,
            )
        )
        if skipped:
            print(t("cli_gamepass_skipped", count=len(skipped)))

        self.last_stats = DiscoveryStats(
            source="gamepass",
            total_api_items=total,
            accepted_count=len(games),
            resolved_count=resolved_count,
            unresolved_count=len(games) - resolved_count,
            skipped_items=skipped,
        )

        return games
