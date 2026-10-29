@echo off
cd /d "%~dp0"

:: ── Read version from version.py ────────────────────────────────────────────
for /f "tokens=3 delims= " %%v in ('findstr "__version__" version.py') do set VERSION=%%v
set VERSION=%VERSION:"=%
echo Building version %VERSION%...
echo.

:: ── Install build dependencies ───────────────────────────────────────────────
echo [1/4] Installing build dependencies...
python -m pip install -r requirements.txt pyinstaller --quiet
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause & exit /b 1
)

:: ── Generate icon.ico from toolbar.png ──────────────────────────────────────
if exist toolbar.png (
    echo [1b/4] Generating icon.ico from toolbar.png...
    python -c "from PIL import Image; img=Image.open('toolbar.png').convert('RGBA'); img.save('icon.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]); print('  icon.ico created')"
) else (
    echo [1b/4] WARNING: toolbar.png not found - skipping icon.ico generation
)

:: ── Frontend: Vite build into frontend\dist ───────────────────────────────────
echo [2/4] Building the frontend...
pushd frontend
call npm ci
if errorlevel 1 (
    popd
    echo ERROR: npm ci failed. Is Node.js 22 installed?
    pause & exit /b 1
)
call npm run build
if errorlevel 1 (
    popd
    echo ERROR: frontend build failed.
    pause & exit /b 1
)
popd

:: ── PyInstaller: one-directory bundle from the spec ──────────────────────────
echo [3/4] Building app bundle (Tyoaikaweleho.spec)...
pyinstaller --noconfirm Tyoaikaweleho.spec
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause & exit /b 1
)

:: ── Inno Setup: create installer ─────────────────────────────────────────────
echo [4/4] Creating installer with Inno Setup...
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
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
