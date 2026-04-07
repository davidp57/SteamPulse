"""GOG Galaxy source plugin.

Discovers games from a GOG account via the GOG OAuth2 API.  Each game is
resolved to a Steam AppID when possible (via the resolver chain); unresolved
games receive a deterministic hash-based synthetic AppID and a non-empty
``external_id``.
"""

from __future__ import annotations

import argparse
import logging
from typing import TYPE_CHECKING

from ..gog_api import gog_auth_with_refresh, gog_get_all_products
from ..i18n import get_translator
from ..models import DiscoveryStats, OwnedGame, SkippedItem, hash_synthetic_appid
from ..resolver import IGDBResolver, SteamStoreResolver, resolve_steam_appid

if TYPE_CHECKING:
    from ..db import Database

log = logging.getLogger(__name__)


class GogSource:
    """Game source plugin for GOG Galaxy.

    Authenticates via a persisted OAuth2 refresh token, fetches the library,
    and resolves each game to a Steam AppID via the resolver chain.
    """

    name = "gog"
    source_labels: frozenset[str] = frozenset({"gog"})
    last_stats: DiscoveryStats | None = None

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Register GOG-specific CLI arguments.

        Args:
            parser: The argument parser to extend.
        """
        parser.add_argument(
            "--gog-refresh-token",
            default=None,
            help="GOG Galaxy OAuth2 refresh token (stored by steam-setup)",
        )

    def is_enabled(self, args: argparse.Namespace) -> bool:
        """Return True if a GOG refresh token is available.

        Args:
            args: Parsed CLI namespace.

        Returns:
            True if ``gog_refresh_token`` is non-empty.
        """
        return bool(getattr(args, "gog_refresh_token", None))

    def discover_games(
        self, args: argparse.Namespace, db: Database | None = None
    ) -> list[OwnedGame]:
        """Discover GOG library and resolve Steam AppIDs.

        Args:
            args: Parsed CLI namespace with ``gog_refresh_token``.
            db: Optional database instance used to cache name→AppID resolutions.

        Returns:
            List of discovered games with source="gog".

        Raises:
            Exception: Re-raises authentication or API errors after printing a
                diagnostic message.
        """
        t = get_translator(getattr(args, "lang", None))
        refresh_token = str(getattr(args, "gog_refresh_token", "") or "")

        # ── Authentication ─────────────────────────────────────────────
        try:
            token = gog_auth_with_refresh(refresh_token)
        except Exception as exc:  # noqa: BLE001
            print(t("cli_gog_auth_error", error=exc))
            raise

        # Persist the rotated refresh token so the CLI saves it after the run.
        args.gog_refresh_token = token.refresh_token
        print(t("cli_gog_authenticated"))

        # ── Library fetch ──────────────────────────────────────────────
        try:
            products = gog_get_all_products(token.access_token)
        except Exception as exc:  # noqa: BLE001
            print(t("cli_gog_library_error", error=exc))
            raise

        print(t("cli_gog_library_count", count=len(products)))

        if not products:
            self.last_stats = DiscoveryStats(
                source="gog",
                total_api_items=0,
                accepted_count=0,
                resolved_count=0,
                unresolved_count=0,
                skipped_items=[],
            )
            return []

        # ── Build resolver chain ───────────────────────────────────────
        resolvers: list[SteamStoreResolver | IGDBResolver] = [SteamStoreResolver()]
        twitch_id = getattr(args, "twitch_client_id", None)
        twitch_secret = getattr(args, "twitch_client_secret", None)
        if twitch_id and twitch_secret:
            resolvers.append(IGDBResolver(str(twitch_id), str(twitch_secret)))

        # ── Resolve each game ──────────────────────────────────────────
        print(t("cli_gog_resolving"))
        games: list[OwnedGame] = []
        resolved_count = 0
        skipped: list[SkippedItem] = []
        total = len(products)
        width = len(str(total))

        for idx, product in enumerate(products, 1):
            name = product.title.strip()
            gog_id = str(product.id)

            if not name:
                skipped.append(SkippedItem(catalog_id=gog_id, raw_name="", reason="no_title"))
                continue

            print(f"\r   [{idx:>{width}}/{total}] {name[:55]:<55}", end="", flush=True)

            external_id = f"gog:{gog_id}"
            steam_appid: int | None = None
            if db is not None:
                steam_appid = db.get_appid_mapping("gog", external_id)
            if steam_appid is None:
                steam_appid = resolve_steam_appid(name, resolvers)
                if db is not None:
                    db.upsert_appid_mapping("gog", external_id, name, steam_appid)

            appid = steam_appid if steam_appid is not None else hash_synthetic_appid(gog_id)
            if steam_appid is not None:
                resolved_count += 1

            games.append(
                OwnedGame(
                    appid=appid,
                    name=name,
                    source="gog",
                    external_id=external_id,
                )
            )

        print()  # newline after the progress line
        print(
            t(
                "cli_gog_resolved_done",
                resolved=resolved_count,
                total=len(games),
                unresolved=len(games) - resolved_count,
            )
        )
        if skipped:
            print(t("cli_gog_skipped", count=len(skipped)))

        self.last_stats = DiscoveryStats(
            source="gog",
            total_api_items=total,
            accepted_count=len(games),
            resolved_count=resolved_count,
            unresolved_count=len(games) - resolved_count,
            skipped_items=skipped,
        )

        return games
