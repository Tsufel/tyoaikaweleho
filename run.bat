@echo off
cd /d "%~dp0"
python -c "import webview, openpyxl" 2>nul || (
    echo Installing dependencies...
    python -m pip install -r requirements.txt --quiet
)
rem rebuild when there is no build yet or any frontend source is newer than it
python -c "import os,sys;t=os.path.getmtime('frontend/dist/index.html');s=['frontend/'+f for f in ('index.html','package.json','package-lock.json','vite.config.ts','svelte.config.js','tsconfig.json')]+[os.path.join(r,f) for r,_,fs in os.walk('frontend/src') for f in fs];sys.exit(any(os.path.getmtime(p)>t for p in s if os.path.exists(p)))" 2>nul || (
    echo Building the frontend...
    pushd frontend
    python -c "import os,sys;sys.exit(os.path.getmtime('package-lock.json')>os.path.getmtime('node_modules/.package-lock.json'))" 2>nul || (
        call npm ci || (popd & echo ERROR: npm ci failed. Is Node.js 22 installed? & pause & exit /b 1)
    )
    call npm run build || (popd & echo ERROR: frontend build failed. & pause & exit /b 1)
    popd
)
python main.py %*
