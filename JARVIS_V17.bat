@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo  JARVIS V17 - UNIFIED AUTONOMOUS OPTIONS WORKSTATION
echo ============================================================

if not exist ".venv\Scripts\python.exe" (
    echo V17 virtual environment is not installed.
    echo Run: powershell -ExecutionPolicy Bypass -File .\install_v17.ps1
    pause
    exit /b 1
)

set JARVIS_LIVE_EXECUTION=0
set JARVIS_V17_AUTONOMOUS_OPTIONS=1

echo Applying V17 direct-pull runtime guards...
".venv\Scripts\python.exe" scripts\apply_v17_release_patches.py
if errorlevel 1 (
    echo.
    echo V17 runtime guard patch failed. JARVIS will not start with a partially patched data path.
    pause
    exit /b 21
)

".venv\Scripts\python.exe" scripts\apply_v17_stability_patches.py
if errorlevel 1 (
    echo.
    echo V17 browser/runtime stability patch failed. JARVIS will not start with a partially patched UI data path.
    pause
    exit /b 22
)

".venv\Scripts\python.exe" -m scripts.jarvis_runtime_supervisor_v17
set EXIT_CODE=%ERRORLEVEL%

if not "%EXIT_CODE%"=="0" (
    echo.
    echo JARVIS V17 exited with code %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%
