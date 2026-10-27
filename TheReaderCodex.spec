# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

project_dir = Path(SPECPATH).resolve()

datas = [(str(project_dir / "assets"), "assets")]
binaries = []
hiddenimports = [
    "googleapiclient.discovery",
    "googleapiclient.http",
    "google.auth.transport.requests",
    "google.oauth2.credentials",
    "google.oauth2.service_account",
    "google_auth_oauthlib.flow",
]

ctk_datas, ctk_binaries, ctk_hidden = collect_all("customtkinter")
datas += ctk_datas
binaries += ctk_binaries
hiddenimports += ctk_hidden

analysis = Analysis(
    [str(project_dir / "main.py")],
    pathex=[str(project_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="TheReaderCodex",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_dir / "assets" / "TheReaderCodex.ico"),
    version=str(project_dir / "build" / "version_info.txt"),
    uac_admin=False,
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TheReaderCodex",
)
