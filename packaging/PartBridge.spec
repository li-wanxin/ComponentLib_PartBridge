# -*- mode: python ; coding: utf-8 -*-
# PartBridge 安装版打包配置（PyInstaller onedir 目录式）
# 用法：pyinstaller packaging/PartBridge.spec --distpath release/dist --workpath build
#
# 安装版采用目录式打包：运行时直接从安装目录加载 DLL，不再每次启动解压到
# %TEMP%\_MEIxxx，根治杀软首扫竞态导致的
# "Failed to load Python DLL ... 找不到指定的模块" 偶发错误（Lab Console 同款修复）。

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
    [],
    exclude_binaries=True,
    name="PartBridge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=os.path.join(ROOT, "app", "app.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PartBridge",
)
