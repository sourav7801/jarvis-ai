@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo  JARVIS V19 - WORKSPACE OS / QUANT TRADING TERMINAL
echo ============================================================

if not exist ".venv\Scripts\python.exe" (
    echo V19 virtual environment is not installed.
    echo Run: powershell -ExecutionPolicy Bypass -File .\install_v17.ps1
    pause
    exit /b 1
)

rem V19 keeps V17's proven market/data safety boundary and adds the
rem V19 workspace operating system on top of it.
set JARVIS_LIVE_EXECUTION=0
set JARVIS_V17_AUTONOMOUS_OPTIONS=1
set JARVIS_V19_WORKSPACE_OS=1

if not exist ".venv-nautilus-new\Scripts\python.exe" (
    echo Preparing isolated NautilusTrader runtime...
    ".venv\Scripts\python.exe" -m venv ".venv-nautilus-new"
    if errorlevel 1 exit /b 26
    ".venv-nautilus-new\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade pip wheel
    if errorlevel 1 exit /b 26
)

".venv-nautilus-new\Scripts\python.exe" -c "import nautilus_trader" >nul 2>&1
if errorlevel 1 (
    echo Installing NautilusTrader 1.231.0 into the isolated runtime...
    ".venv-nautilus-new\Scripts\python.exe" -m pip install --disable-pip-version-check -r ".\requirements-nautilus.txt"
    if errorlevel 1 (
        echo NautilusTrader installation failed.
        pause
        exit /b 26
    )
)

echo Applying canonical V17 market/data safety guards...
".venv\Scripts\python.exe" scripts\apply_v17_release_patches.py
if errorlevel 1 exit /b 21
".venv\Scripts\python.exe" scripts\apply_v17_stability_patches.py
if errorlevel 1 exit /b 22
".venv\Scripts\python.exe" scripts\apply_v17_history_snapshot_patches.py
if errorlevel 1 exit /b 24
".venv\Scripts\python.exe" scripts\apply_v17_market_session_patches.py
if errorlevel 1 exit /b 23
".venv\Scripts\python.exe" scripts\apply_v17_crypto_paper_patches.py
if errorlevel 1 exit /b 25

echo Starting JARVIS V19 Workspace OS...
".venv\Scripts\python.exe" -m scripts.jarvis_runtime_supervisor_v17
set EXIT_CODE=%ERRORLEVEL%

if not "%EXIT_CODE%"=="0" (
    echo.
    echo JARVIS V19 exited with code %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%
