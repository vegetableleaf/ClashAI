@echo off
rem ============================================================================
rem  ClashAI -- double-click this file. It is the only starter in this folder.
rem
rem  It opens the control panel in its own window. Everything else (recording,
rem  labelling, training, playing) is a button in there; you never need a
rem  terminal. A local server runs on 127.0.0.1 only -- nothing is exposed to
rem  the network and nothing is uploaded.
rem
rem  Keep this console window open while you work; closing it stops the panel.
rem
rem  ClashAI.exe, if present, does exactly the same with a nicer icon.
rem  Build it with tools\build_exe.bat.
rem ============================================================================
setlocal
cd /d "%~dp0icebow"

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   No Python environment yet. This is a one-time setup, about 5 minutes:
  echo.
  echo     py -3.11 -m venv icebow\.venv
  echo     icebow\.venv\Scripts\python.exe -m pip install -r icebow\requirements.txt
  echo.
  echo   Run those from the folder ABOVE this one, then double-click ClashAI.bat again.
  echo   Full instructions: SETUP.md in the repo root.
  echo.
  pause
  exit /b 1
)

.venv\Scripts\python.exe -c "import flask" >nul 2>&1
if errorlevel 1 (
  echo [ClashAI] Flask is missing - installing it once into the environment ...
  .venv\Scripts\python.exe -m pip install "Flask>=3.0"
  if errorlevel 1 (
    echo [ClashAI] Install failed. Try manually:
    echo           icebow\.venv\Scripts\python.exe -m pip install Flask
    pause
    exit /b 1
  )
)

echo [ClashAI] Opening the control panel ... keep this window open, Ctrl+C stops it.
.venv\Scripts\python.exe run.py ui %*
echo.
echo [ClashAI] Panel closed.
pause
