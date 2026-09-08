@echo off
setlocal

cd /d C:\Jarvis

title JARVIS OS V8 MASTER + V15 AUTONOMOUS MARKET REASONING

REM JARVIS V15 fast-path: if the exact current runtime already exists, do not
REM start another voice process or supervisor. Open the protected dashboard and exit.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ok=$false; try {$r=Invoke-RestMethod 'http://127.0.0.1:8797/api/v15/paper-authority' -TimeoutSec 2; $ok=($r.success -eq $true -and $r.version -eq '15.0' -and $r.service -eq 'JARVIS_MASTER_V15_AUTONOMOUS_MARKET_REASONING_BRIDGE')} catch {}; if($ok){Start-Process 'http://127.0.0.1:8797'; exit 0}else{exit 1}" >nul 2>&1
if not errorlevel 1 (
    echo JARVIS V15 is already running. Opening the existing dashboard.
    exit /b 0
)

set "JARVIS_PY=C:\Jarvis\.venv\Scripts\python.exe"
if exist "%JARVIS_PY%" "%JARVIS_PY%" -c "import omni, numpy, pandas, workstation.jarvis_os_v3, workstation.jarvis_os_v8, workstation.completion_console_v15" >nul 2>&1
if errorlevel 1 set "JARVIS_PY=C:\Jarvis\.venv-new\Scripts\python.exe"
if exist "%JARVIS_PY%" "%JARVIS_PY%" -c "import omni, numpy, pandas, workstation.jarvis_os_v3, workstation.jarvis_os_v8, workstation.completion_console_v15" >nul 2>&1

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

REM JARVIS_RUNTIME_SUPERVISOR_V15
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v62
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v8
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v11
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v12
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v13
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v14
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v141
REM Historical protected launcher contracts retained for cross-generation tests:
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v8
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v11
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v12
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v13
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v14
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v141
REM Preserves V6.2 stale-process ownership, V8 protected Master identity, V11 execution mesh, V12 adaptive EV, V13 context, V14 continuous execution and V14.1 verified risk geometry.
REM V15 adds market beliefs, competing hypotheses, portfolio opportunity cost, causal review and single-supervisor safety.
REM Master remains the protected V8 Unified Intelligence HTTP/UI runtime on port 8797.
REM Fractional sizing remains constraint-aware; Paper Desk remains final risk authority.
REM No live broker-order surface is added by this launcher.
"%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v15

if errorlevel 1 (
    echo.
    echo JARVIS V15 exited with an error.
    pause
)

endlocal
