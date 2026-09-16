@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo  JARVIS V17 - AUTONOMOUS OPTIONS PAPER RUNTIME
echo ============================================================

if not exist ".venv\Scripts\python.exe" (
    echo V17 virtual environment is not installed.
    echo Run: powershell -ExecutionPolicy Bypass -File .\install_v17.ps1
    pause
    exit /b 1
)

set JARVIS_LIVE_EXECUTION=0
set JARVIS_V17_AUTONOMOUS_OPTIONS=1
".venv\Scripts\python.exe" "start_jarvis_professional_terminal_v17.py"
set EXIT_CODE=%ERRORLEVEL%

if not "%EXIT_CODE%"=="0" (
    echo.
    echo JARVIS V17 exited with code %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%
