# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

ROOT_DIR = Path(SPECPATH).resolve()

datas = [
    (str(ROOT_DIR / 'web_app' / 'templates'), 'web_app/templates'),
    (str(ROOT_DIR / 'web_app' / 'static'), 'web_app/static'),
    (str(ROOT_DIR / 'web_app'), 'web_app')
]
binaries = []
hiddenimports = [
    'web_app',
    'web_app.app',
    'web_app.spotify_engine',
    'web_app.apple_music_engine',
    'web_app.audio_processor',
    'web_app.security_engine',
    'web_app.updater_engine',
    'pythonnet',
    'clr_loader'
]

for pkg in ['web_app', 'fastapi', 'uvicorn', 'yt_dlp', 'starlette', 'pydantic', 'websockets', 'mutagen', 'webview']:
    tmp_ret = collect_all(pkg)
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]

a = Analysis(
    [str(ROOT_DIR / 'main_desktop.py')],
    pathex=[str(ROOT_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NexoDownload',
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
    icon=[str(ROOT_DIR / 'web_app' / 'static' / 'icons' / 'app_icon.ico')],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NexoDownload',
)
