"""Game source plugin system.

A *game source* is responsible for discovering which games a user owns, has
wishlisted, or follows on a particular store.  All data enrichment (app
details, news) is always performed via Steam, regardless of which source
discovered the game.

Implementing a new source
-------------------------
Create a module under ``steam_tracker/sources/`` (e.g. ``gog.py``) with a
class that satisfies :class:`GameSource`, then add an instance to the
``_SOURCES`` list in this module.

Example::

    class GogSource:
        name = "gog"

        def add_arguments(self, parser: argparse.ArgumentParser) -> None:
            parser.add_argument("--gog-token", help="GOG OAuth token")

        def is_enabled(self, args: argparse.Namespace) -> bool:
            return bool(getattr(args, "gog_token", None))

        def discover_games(self, args: argparse.Namespace) -> list[OwnedGame]:
            ...
"""
from __future__ import annotations

import argparse
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..models import OwnedGame


@runtime_checkable
class GameSource(Protocol):
    """Protocol for game discovery plugins.

    A :class:`GameSource` discovers the games a user owns/wishlists/follows on
    one store and returns them as :class:`~steam_tracker.models.OwnedGame`
    instances.  The caller (CLI) passes all discovered games to the Steam
    enrichment pipeline (app details, news) and persists them to the database.

    Note:
        ``discover_games`` may return the same ``appid`` multiple times under
        different ``source`` values (e.g. ``"owned"`` and ``"wishlist"``).
        The caller is responsible for deduplication before passing the list to
        the fetcher; the :class:`~steam_tracker.db.Database` ``upsert_game``
        method handles source priority (``owned > wishlist > followed``).
    """

    name: str
    """Unique identifier for this source (e.g. ``"steam"``, ``"gog"``)."""

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Register CLI arguments specific to this source.

        Args:
            parser: The argument parser to extend.
        """
        ...

    def is_enabled(self, args: argparse.Namespace) -> bool:
        """Return ``True`` if this source should run for the given CLI args.

        Args:
            args: Parsed CLI namespace (after all sources have added arguments).
        """
        ...

    def discover_games(self, args: argparse.Namespace) -> list[OwnedGame]:
        """Discover all games for this source and return them.

        The returned list may contain the same ``appid`` with different
        ``source`` labels (e.g. a game that is both owned and wishlisted).
        The caller handles cross-source and cross-plugin deduplication.

        Args:
            args: Parsed CLI namespace.

        Returns:
            All :class:`~steam_tracker.models.OwnedGame` instances found.
        """
        ...


def get_all_sources() -> list[GameSource]:
    """Return all registered game source plugins.

    Returns:
        A new list containing one instance of every registered
        :class:`GameSource`.  Modifying the returned list does not affect the
        internal registry.
    """
    from .epic import EpicSource  # local imports avoid circular dependency
    from .steam import SteamSource

    return [SteamSource(), EpicSource()]
