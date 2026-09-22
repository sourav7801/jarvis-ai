@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo  JARVIS V20 - FULL WORKSPACE OPERATING SYSTEM
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv is missing.
  pause
  exit /b 1
)

echo [1/4] Checking Git branch...
".venv\Scripts\python.exe" -c "import pathlib; print('Repo:', pathlib.Path('.').resolve())"

echo [2/4] Releasing only the process currently serving Quant port 8787...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8787" ^| findstr "LISTENING"') do (
  echo Stopping PID %%P on port 8787...
  taskkill /F /PID %%P >nul 2>&1
)

set JARVIS_LIVE_EXECUTION=0
set JARVIS_V17_AUTONOMOUS_OPTIONS=1
set JARVIS_V19_WORKSPACE_OS=0
set JARVIS_V20_WORKSPACE_OS=1

echo [3/4] Applying canonical V17 data/safety guards...
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

echo [4/4] Starting JARVIS V20...
".venv\Scripts\python.exe" -m scripts.jarvis_runtime_supervisor_v17
set EXIT_CODE=%ERRORLEVEL%

echo.
if "%EXIT_CODE%"=="0" (
  echo JARVIS V20 supervisor exited normally.
) else (
  echo JARVIS V20 exited with code %EXIT_CODE%.
  pause
)
exit /b %EXIT_CODE%
