@echo off
rem ClashAI launcher -- double-click this file to open the control panel in your browser.
rem It only starts a LOCAL server on 127.0.0.1; nothing is exposed to the network.
setlocal
cd /d "%~dp0icebow"

if not exist ".venv\Scripts\python.exe" (
  echo [start_ui] Keine virtuelle Umgebung gefunden: %CD%\.venv
  echo [start_ui] Anlegen mit:  py -3.11 -m venv .venv ^&^& .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)

.venv\Scripts\python.exe -c "import flask" >nul 2>&1
if errorlevel 1 (
  echo [start_ui] Flask fehlt - installiere es einmalig in die venv ...
  .venv\Scripts\python.exe -m pip install "Flask>=3.0"
  if errorlevel 1 (
    echo [start_ui] Installation fehlgeschlagen. Manuell:  .venv\Scripts\python.exe -m pip install Flask
    pause
    exit /b 1
  )
)

echo [start_ui] Starte Launcher ... (dieses Fenster offen lassen; Strg+C beendet ihn)
.venv\Scripts\python.exe run.py ui %*
echo.
echo [start_ui] Launcher beendet.
pause
