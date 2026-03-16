"""Epic Games Store source plugin.

Discovers games from an Epic account via the Epic OAuth2 API and library
endpoint.  Each game is resolved to a Steam AppID when possible (via the
resolver chain); unresolved games receive a deterministic hash-based appid
and a non-empty ``external_id``.
"""
from __future__ import annotations

import argparse
import hashlib
import logging

from ..epic_api import epic_auth_with_code, epic_auth_with_device, epic_get_library
from ..i18n import get_translator
from ..models import SYNTHETIC_APPID_BASE, OwnedGame
from ..resolver import SteamStoreResolver, resolve_steam_appid

log = logging.getLogger(__name__)

_HASH_APPID_RANGE = 100_000_000


def _hash_appid(catalog_item_id: str) -> int:
    """Generate a deterministic appid in the reserved range for unresolved games."""
    digest = hashlib.sha256(catalog_item_id.encode()).hexdigest()
    return SYNTHETIC_APPID_BASE + int(digest[:8], 16) % _HASH_APPID_RANGE


class EpicSource:
    """Game source plugin for Epic Games Store.

    Authenticates via authorization code (first run) or persisted device
    credentials (subsequent runs), fetches the library, and resolves each
    game to a Steam AppID via the resolver chain.
    """

    name = "epic"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Register Epic-specific CLI arguments.

        Args:
            parser: The argument parser to extend.
        """
        parser.add_argument(
            "--epic-auth-code",
            default=None,
            help="Epic Games one-time authorization code for first login",
        )
        parser.add_argument(
            "--epic-device-id",
            default=None,
            help="Epic Games device ID (for persistent auth)",
        )
        parser.add_argument(
            "--epic-account-id",
            default=None,
            help="Epic Games account ID (for persistent auth)",
        )
        parser.add_argument(
            "--epic-device-secret",
            default=None,
            help="Epic Games device secret (for persistent auth)",
        )
        parser.add_argument(
            "--twitch-client-id",
            default=None,
            help="Twitch/IGDB client ID (for IGDB resolver)",
        )
        parser.add_argument(
            "--twitch-client-secret",
            default=None,
            help="Twitch/IGDB client secret (for IGDB resolver)",
        )

    def is_enabled(self, args: argparse.Namespace) -> bool:
        """Return True if Epic credentials are provided.

        Args:
            args: Parsed CLI namespace.

        Returns:
            True if an auth code or device credentials are provided.
        """
        if getattr(args, "epic_auth_code", None):
            return True
        # Device auth requires all three fields
        return bool(
            getattr(args, "epic_device_id", None)
            and getattr(args, "epic_account_id", None)
            and getattr(args, "epic_device_secret", None)
        )

    def discover_games(self, args: argparse.Namespace) -> list[OwnedGame]:
        """Discover Epic Games library and resolve Steam AppIDs.

        Args:
            args: Parsed CLI namespace with Epic credentials.

        Returns:
            List of discovered games with source="epic".
        """
        t = get_translator(getattr(args, "lang", None))

        # ── Authentication ─────────────────────────────────────────────
        try:
            token_data = self._authenticate(args)
        except Exception as exc:  # noqa: BLE001
            print(t("cli_epic_auth_error", error=exc))
            return []

        access_token: str = str(token_data["access_token"])
        print(t("cli_epic_authenticated"))

        # ── Library fetch ──────────────────────────────────────────────
        try:
            library_items = epic_get_library(access_token)
        except Exception as exc:  # noqa: BLE001
            print(t("cli_epic_library_error", error=exc))
            return []

        print(t("cli_epic_library_count", count=len(library_items)))

        # ── Build resolvers ────────────────────────────────────────────
        resolvers = [SteamStoreResolver()]

        # ── Resolve each game ──────────────────────────────────────────
        print(t("cli_epic_resolving"))
        games: list[OwnedGame] = []
        resolved_count = 0
        total = len(library_items)
        width = len(str(total))
        for idx, item in enumerate(library_items, 1):
            catalog_id = str(item.get("catalogItemId", ""))
            # `appName` is an internal codename (e.g. "Petrel"); prefer the
            # human-readable title from metadata when available.
            internal_name = str(item.get("appName", ""))
            metadata = item.get("metadata") or {}
            name = str(metadata.get("title", "") or internal_name)
            if not catalog_id or not name:
                continue
            log.debug("Epic item: internal=%r  title=%r", internal_name, name)

            print(f"\r   [{idx:>{width}}/{total}] {name[:55]:<55}", end="", flush=True)
            steam_appid = resolve_steam_appid(name, resolvers)
            appid = steam_appid if steam_appid is not None else _hash_appid(catalog_id)
            if steam_appid is not None:
                resolved_count += 1

            games.append(
                OwnedGame(
                    appid=appid,
                    name=name,
                    source="epic",
                    external_id=f"epic:{catalog_id}",
                )
            )

        print()  # newline after the \r progress line
        print(t("cli_epic_resolved_done", resolved=resolved_count, total=len(games),
                unresolved=len(games) - resolved_count))

        return games

    def _authenticate(self, args: argparse.Namespace) -> dict[str, object]:
        """Authenticate with Epic using available credentials.

        Args:
            args: Parsed CLI namespace.

        Returns:
            Token response dict with access_token and account_id.
        """
        auth_code = getattr(args, "epic_auth_code", None)
        if auth_code:
            return epic_auth_with_code(auth_code)

        return epic_auth_with_device(
            device_id=str(getattr(args, "epic_device_id", "")),
            account_id=str(getattr(args, "epic_account_id", "")),
            secret=str(getattr(args, "epic_device_secret", "")),
        )
