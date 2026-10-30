# -*- mode: python ; coding: utf-8 -*-
# Single build definition: pyinstaller Tyoaikaweleho.spec
# Build the frontend first (cd frontend && npm ci && npm run build).
import os

from PyInstaller.utils.hooks import collect_all

if not os.path.isfile(os.path.join('frontend', 'dist', 'index.html')):
    raise SystemExit('frontend/dist is missing - run "npm ci && npm run build" in frontend first')

# splash.png/toolbar.png stay in the repo (README, build.bat's icon.ico step);
# the UI uses frontend/src/assets/*.webp, so they are not bundled.
datas = [('frontend/dist', 'webui'), ('icon.ico', '.')]
binaries = []
hiddenimports = ['winrt.windows.media.ocr', 'winrt.windows.graphics.imaging',
                 'winrt.windows.storage.streams', 'winrt.windows.foundation',
                 'winrt.runtime']
# certifi: cacert.pem for services/net.py's root list
for pkg in ('webview', 'winocr', 'PIL', 'certifi'):
    tmp_ret = collect_all(pkg)
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'customtkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Tyoaikaweleho',
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
    icon=['icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    # .NET assemblies and the WebView2 loader must not be UPX-packed
    upx_exclude=['Python.Runtime.dll', 'WebView2Loader.dll', 'Microsoft.Web.WebView2.Core.dll',
                 'Microsoft.Web.WebView2.WinForms.dll', 'vcruntime140.dll'],
    name='Tyoaikaweleho',
)
