@echo off
rem Builds ClashAI.exe from launcher_exe.py, into the repo root next to ClashAI.bat.
rem You do NOT need this to use ClashAI -- ClashAI.bat already works. The .exe is only a
rem prettier double-click with its own icon. Not tracked in git; rebuild it locally
rem after changing launcher_exe.py.
setlocal
cd /d "%~dp0.."

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
  --icon icebow\ui_icon.ico tools\launcher_exe.py --distpath . --workpath build_tmp --specpath build_tmp -y

echo.
echo [build_exe] Done: ClashAI.exe is in the repo root, next to ClashAI.bat.
pause
