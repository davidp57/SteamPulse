# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for SteamPulse — produces a single standalone executable:
#   dist\steampulse.exe

from PyInstaller.building.api import EXE, PYZ
from PyInstaller.building.build_main import Analysis

a = Analysis(
    ["entry_steampulse.py"],
    pathex=[".."],
    binaries=[],
    datas=[],
    hiddenimports=[
        "steam_tracker.api",
        "steam_tracker.cli",
        "steam_tracker.db",
        "steam_tracker.fetcher",
        "steam_tracker.models",
        "steam_tracker.renderer",
        "pydantic",
        "pydantic.v1",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="steampulse",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
