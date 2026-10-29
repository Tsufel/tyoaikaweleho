@echo off
cd /d "%~dp0"
python -c "import webview, openpyxl" 2>nul || (
    echo Installing dependencies...
    python -m pip install -r requirements.txt --quiet
)
if not exist frontend\dist\index.html (
    echo Building the frontend...
    pushd frontend
    call npm ci || (popd & echo ERROR: npm ci failed. Is Node.js 22 installed? & pause & exit /b 1)
    call npm run build || (popd & echo ERROR: frontend build failed. & pause & exit /b 1)
    popd
)
python main.py %*
