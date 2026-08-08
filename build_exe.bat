@echo off
rem Builds ClashAI.exe from launcher.py -- run this again after changing launcher.py.
rem The .exe itself is not tracked in git (see .gitignore); rebuild it locally whenever needed.
setlocal
cd /d "%~dp0"

if not exist "icebow\.venv\Scripts\python.exe" (
  echo [build_exe] No virtual environment found: icebow\.venv
  echo [build_exe] Create it first: py -3.11 -m venv icebow\.venv ^&^& icebow\.venv\Scripts\python.exe -m pip install -r icebow\requirements.txt
  pause
  exit /b 1
)

icebow\.venv\Scripts\python.exe -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
  echo [build_exe] Installing PyInstaller into the venv (build tool only, not a runtime dependency) ...
  icebow\.venv\Scripts\python.exe -m pip install pyinstaller
)

icebow\.venv\Scripts\python.exe -m PyInstaller --onefile --console --name ClashAI ^
  --icon icebow\ui_icon.ico launcher.py --distpath . --workpath build_tmp --specpath build_tmp -y

echo.
echo [build_exe] Done: ClashAI.exe is in this folder.
pause
