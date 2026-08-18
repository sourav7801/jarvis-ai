@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv-new\Scripts\python.exe" (
  echo JARVIS could not find .venv-new\Scripts\python.exe
  echo Create the Python environment first, then run this launcher again.
  pause
  exit /b 1
)

echo Starting the canonical JARVIS dashboard...
echo Keep this window open. Press Ctrl+C here to stop JARVIS.
".venv-new\Scripts\python.exe" -m scripts.launch_workstation

if errorlevel 1 (
  echo.
  echo JARVIS stopped with an error. If port 8787 is already in use,
  echo close the older JARVIS terminal and run this launcher again.
  pause
)
