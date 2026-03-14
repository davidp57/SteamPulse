"""Entry point wrapper for steam-fetch — used by PyInstaller."""
from steam_tracker.cli import cmd_fetch

if __name__ == "__main__":
    cmd_fetch()
