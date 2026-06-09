@echo off
cd /d "%~dp0"
echo Installing PyInstaller...
pip install pyinstaller --quiet
echo Building Tyoaikaweleho.exe...
pyinstaller --onefile --windowed --name "Tyoaikaweleho" --collect-all customtkinter main.py
echo.
echo Done!  Distribute:  dist\Tyoaikaweleho.exe
echo Upload that file to a GitHub release tagged with the version in version.py
pause
