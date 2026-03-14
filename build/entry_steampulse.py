"""Entry point wrapper for steampulse — used by PyInstaller."""
from steam_tracker.cli import cmd_run

if __name__ == "__main__":
    cmd_run()
