@echo off
setlocal
cd /d "%~dp0.."

set "JARVIS_V17_AUTONOMOUS_OPTIONS=1"
set "JARVIS_LIVE_EXECUTION=0"
set "JARVIS_AUTO_PAPER_START=0"
set "JARVIS_V12_AUTO_PAPER_START=0"
set "JARVIS_NO_BROWSER=0"

set "PY=%CD%\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo JARVIS V17 runtime is not installed correctly.
  echo Run the V17 installer again to repair the local environment.
  pause
  exit /b 31
)

"%PY%" -m scripts.jarvis_runtime_supervisor_v17
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo JARVIS V17 exited with code %RC%.
  pause
)
exit /b %RC%
