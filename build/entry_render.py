"""Entry point wrapper for steam-render — used by PyInstaller."""
from steam_tracker.cli import cmd_render

if __name__ == "__main__":
    cmd_render()
