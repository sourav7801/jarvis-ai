@echo off
setlocal

cd /d C:\Jarvis

title JARVIS OS V8 MASTER + V14.1 RISK-GEOMETRY CONVERGENCE

set "JARVIS_PY=C:\Jarvis\.venv\Scripts\python.exe"
if exist "%JARVIS_PY%" "%JARVIS_PY%" -c "import omni, numpy, pandas, workstation.jarvis_os_v3, workstation.jarvis_os_v8, workstation.completion_console_v141" >nul 2>&1
if errorlevel 1 set "JARVIS_PY=C:\Jarvis\.venv-new\Scripts\python.exe"
if exist "%JARVIS_PY%" "%JARVIS_PY%" -c "import omni, numpy, pandas, workstation.jarvis_os_v3, workstation.jarvis_os_v8, workstation.completion_console_v141" >nul 2>&1

REM JARVIS_NATIVE_VOICE_V32
start "JARVIS Native Voice" /min powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Jarvis\start_jarvis_native_voice.ps1"

if not exist "%JARVIS_PY%" (
    echo.
    echo JARVIS Python environment not found.
    pause
    exit /b 1
)

REM JARVIS_NAUTILUS_QUANT_CORE_V5
REM start_jarvis_nautilus_core.py is owned and restarted by the runtime supervisor.
set "JARVIS_NAUTILUS_PY=C:\Jarvis\.venv-nautilus\Scripts\python.exe"
if exist "%JARVIS_NAUTILUS_PY%" "%JARVIS_NAUTILUS_PY%" -c "import nautilus_trader, nautilus_trader.backtest.config, numpy, pandas; assert nautilus_trader.__version__ == '1.231.0'" >nul 2>&1
if errorlevel 1 set "JARVIS_NAUTILUS_PY=C:\Jarvis\.venv-nautilus-new\Scripts\python.exe"
if exist "%JARVIS_NAUTILUS_PY%" "%JARVIS_NAUTILUS_PY%" -c "import nautilus_trader, nautilus_trader.backtest.config, numpy, pandas; assert nautilus_trader.__version__ == '1.231.0'" >nul 2>&1
if errorlevel 1 set "JARVIS_NAUTILUS_PY=%JARVIS_PY%"

REM JARVIS_RUNTIME_SUPERVISOR_V141
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v62
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v8
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v11
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v12
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v13
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v14
REM Historical protected launcher contracts retained for cross-generation tests:
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v8
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v11
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v12
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v13
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v14
REM Preserves V6.2 stale-Quant ownership, V8 protected Master identity, V11 execution mesh, V12 adaptive EV, V13 contextual intelligence and V14 continuous execution.
REM Master remains the protected V8 Unified Intelligence HTTP/UI runtime on port 8797.
REM V14.1 reconstructs entry/stop/target only from verified completed-bar evidence before V14 EV evaluation.
REM INVALID_RISK_LEVELS remains hard when verified geometry cannot be built.
REM Fractional sizing remains constraint-aware; Paper Desk remains final risk authority.
REM No live broker-order surface is added by this launcher.
"%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v141

if errorlevel 1 (
    echo.
    echo JARVIS V14.1 exited with an error.
    pause
)

endlocal
