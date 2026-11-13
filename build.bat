@echo off
rem Builds dist\FlasH\FlasH.exe (folder build: starts faster on weak PCs than --onefile).
setlocal
cd /d "%~dp0"
py -m pip install --upgrade -r requirements.txt pyinstaller || exit /b 1
py -m PyInstaller --noconfirm --clean --windowed --name FlasH ^
  --exclude-module numpy --exclude-module PIL --exclude-module matplotlib ^
  run_flash.py || exit /b 1
echo.
echo Done: dist\FlasH\FlasH.exe
