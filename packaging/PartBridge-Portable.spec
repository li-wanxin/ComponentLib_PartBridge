# -*- mode: python ; coding: utf-8 -*-
# PartBridge 绿色免安装版打包配置（PyInstaller onefile 单文件）
# 用法：pyinstaller packaging/PartBridge-Portable.spec --distpath release/portable --workpath build

import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

a = Analysis(
    [os.path.join(ROOT, "app", "desktop.py")],
    pathex=[os.path.join(ROOT, "app")],
    binaries=[],
    datas=[(os.path.join(ROOT, "app", "web"), "web")],
    hiddenimports=[
        "pyodbc",
        "olefile",
        "webview.platforms.edgechromium",
        "lcsc3d.eda.altium",
        "lcsc3d.eda.library_merge",
        "lcsc3d.eda.easyeda_import",
        "lcsc3d.eda.compound_storage",
        "lcsc3d.services.store",
        "lcsc3d.services.store_session",
        "lcsc3d.services.store_crypto",
        "gmalg",
        "certifi",
        "urllib3",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "PIL", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PartBridge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=os.path.join(ROOT, "app", "app.ico"),
)
