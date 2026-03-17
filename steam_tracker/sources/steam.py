"""Steam game source plugin.

Discovers games from a Steam account via three sub-sources:

- **owned** — full library via ``IPlayerService/GetOwnedGames``
- **wishlist** — items via ``IWishlistService/GetWishlist`` (default: enabled)
- **followed** — followed games via ``IPlayerService/GetFollowedGames``
  (opt-in via ``--followed``; the endpoint is not publicly accessible for all
  accounts)
"""
from __future__ import annotations

import argparse
import logging
from typing import TYPE_CHECKING

from ..api import get_followed_games, get_owned_games, get_wishlist
from ..i18n import get_translator
from ..models import OwnedGame

if TYPE_CHECKING:
    from ..db import Database

log = logging.getLogger(__name__)


class SteamSource:
    """Game source plugin for Steam (owned library, wishlist, followed games).

    This source is always enabled.  It registers ``--key``, ``--steamid``,
    ``--no-wishlist``, and ``--followed`` CLI arguments.

    Note:
        The returned list from :meth:`discover_games` may contain the same
        ``appid`` under both ``"owned"`` and ``"wishlist"`` (or ``"followed"``)
        source labels.  The caller is responsible for deduplicating before
        passing games to the fetcher; the database's ``upsert_game`` enforces
        source priority (``owned > wishlist > followed``).
    """

    name = "steam"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Register Steam-specific CLI arguments.

        Args:
            parser: The argument parser to extend.
        """
        parser.add_argument(
            "--key",
            required=False,
            default=None,
            help="Steam Web API key (or set via config file)",
        )
        parser.add_argument(
            "--steamid",
            required=False,
            default=None,
            help="SteamID64 (or set via config file)",
        )
        parser.add_argument(
            "--no-wishlist",
            action="store_true",
            help="Skip wishlist fetch",
        )
        parser.add_argument(
            "--followed",
            action="store_true",
            help="Fetch followed games (may not be publicly available for all accounts)",
        )

    def is_enabled(self, args: argparse.Namespace) -> bool:
        """Steam source is always enabled.

        Args:
            args: Parsed CLI namespace (unused).

        Returns:
            Always ``True``.
        """
        return True

    def discover_games(
        self, args: argparse.Namespace, db: Database | None = None
    ) -> list[OwnedGame]:
        """Discover Steam games (owned, wishlist, followed) for the given account.

        Prints progress messages to stdout using the translator for ``args.lang``.

        Args:
            args: Parsed CLI namespace; must include ``key``, ``steamid``,
                ``no_wishlist``, ``followed``, and ``lang`` attributes.
            db: Unused; accepted for protocol compatibility.

        Returns:
            All discovered :class:`~steam_tracker.models.OwnedGame` instances,
            possibly with duplicate ``appid`` values under different ``source``
            labels.  Order: owned → wishlist → followed.
        """
        t = get_translator(getattr(args, "lang", None))
        games: list[OwnedGame] = []

        # ── Owned library ──────────────────────────────────────────────────
        print(t("cli_fetching_library"))
        owned = get_owned_games(args.key, args.steamid)
        print(t("cli_owned_count", count=len(owned)))
        games.extend(owned)
        owned_appids: set[int] = {g.appid for g in owned}

        # ── Wishlist ───────────────────────────────────────────────────────
        if not getattr(args, "no_wishlist", False):
            print(t("cli_fetching_wishlist"))
            try:
                wishlist = get_wishlist(args.key, args.steamid)
                new_wl = [g for g in wishlist if g.appid not in owned_appids]
                games.extend(wishlist)
                print(t("cli_wishlist_count", total=len(wishlist), new=len(new_wl)))
            except Exception as exc:  # noqa: BLE001
                print(t("cli_wishlist_error", error=exc))
                wishlist = []
        else:
            wishlist = []

        # ── Followed games ─────────────────────────────────────────────────
        if getattr(args, "followed", False):
            print(t("cli_fetching_followed"))
            try:
                followed = get_followed_games(args.key, args.steamid)
                seen_so_far = owned_appids | {g.appid for g in wishlist}
                new_fol = [g for g in followed if g.appid not in seen_so_far]
                games.extend(followed)
                print(t("cli_followed_count", total=len(followed), new=len(new_fol)))
            except Exception as exc:  # noqa: BLE001
                print(t("cli_followed_error", error=exc))

        return games
