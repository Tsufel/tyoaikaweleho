@echo off
cd /d "%~dp0"

:: ── Read version from version.py ────────────────────────────────────────────
for /f "tokens=3 delims= " %%v in ('findstr "__version__" version.py') do set VERSION=%%v
set VERSION=%VERSION:"=%
echo Building version %VERSION%...
echo.

:: ── Install build dependencies ───────────────────────────────────────────────
echo [1/3] Installing build dependencies...
pip install pyinstaller winocr Pillow customtkinter openpyxl --quiet
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause & exit /b 1
)

:: ── Generate icon.ico from toolbar.png ──────────────────────────────────────
if exist toolbar.png (
    echo [1b/3] Generating icon.ico from toolbar.png...
    python -c "from PIL import Image; img=Image.open('toolbar.png').convert('RGBA'); img.save('icon.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]); print('  icon.ico created')"
) else (
    echo [1b/3] WARNING: toolbar.png not found - skipping icon.ico generation
)

:: ── PyInstaller: one-directory bundle ────────────────────────────────────────
echo [2/3] Building app bundle (--onedir)...
pyinstaller --onedir --windowed --name "Tyoaikaweleho" ^
    --collect-all customtkinter ^
    --collect-all winocr ^
    --collect-all PIL ^
    --hidden-import winrt.windows.media.ocr ^
    --hidden-import winrt.windows.graphics.imaging ^
    --hidden-import winrt.windows.foundation ^
    --hidden-import winrt.runtime ^
    --add-data "splash.png;." ^
    --add-data "toolbar.png;." ^
    --add-data "icon.ico;." ^
    main.py
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause & exit /b 1
)

:: ── Inno Setup: create installer ─────────────────────────────────────────────
echo [3/3] Creating installer with Inno Setup...
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    echo.
    echo ERROR: Inno Setup 6 not found.
    echo Download it free from: https://jrsoftware.org/isdl.php
    echo Then re-run this script.
    pause & exit /b 1
)
%ISCC% /DAppVersion=%VERSION% installer.iss
if errorlevel 1 (
    echo ERROR: Inno Setup compilation failed.
    pause & exit /b 1
)

echo.
echo ============================================================
echo  Done!
echo  Installer: Output\TyoaikawelehoSetup_%VERSION%.exe
echo.
echo  Upload that file to a GitHub Release tagged v%VERSION%
echo ============================================================
pause
