@echo off
cd /d "%~dp0"
python -c "import customtkinter, openpyxl" 2>nul || (
    echo Installing dependencies...
    python -m pip install -r requirements.txt --quiet
)
python main.py
