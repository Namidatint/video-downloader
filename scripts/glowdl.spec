# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for 视频下载器 (Windows / macOS, one-dir build)."""

import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))
IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
EXE_ICON = os.path.join(ROOT, "app", "resources", "icon.ico") if IS_WIN else None
ICNS = os.path.join(ROOT, "app", "resources", "icon.icns")

datas = collect_data_files("imageio_ffmpeg")
datas += collect_data_files("certifi")
datas += [(os.path.join(ROOT, "app", "resources"), "app/resources")]

hiddenimports = collect_submodules("yt_dlp")
hiddenimports += ["certifi", "mutagen", "Cryptodome", "websocket"]

a = Analysis(
    [os.path.join(ROOT, "app", "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="视频下载器",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=EXE_ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="视频下载器",
)

if IS_MAC:
    app = BUNDLE(
        coll,
        name="视频下载器.app",
        icon=ICNS,
        bundle_identifier="com.namidatint.videodownloader",
        info_plist={
            "CFBundleDisplayName": "视频下载器",
            "CFBundleName": "视频下载器",
            "CFBundleShortVersionString": "1.0.2",
            "CFBundleVersion": "1.0.2",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSHumanReadableCopyright": "by NamidaTint · 仅用于下载你有权保存的内容",
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeName": "Video URL",
                    "CFBundleTypeRole": "Viewer",
                    "LSItemContentTypes": ["public.url"],
                }
            ],
        },
    )
