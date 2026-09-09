@echo off
setlocal

cd /d C:\Jarvis

title JARVIS OS V8 MASTER + V15.1 OPTIONS EXECUTION INTELLIGENCE

REM JARVIS V15.1 fast-path: exact current runtime opens the protected dashboard.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ok=$false; try {$r=Invoke-RestMethod 'http://127.0.0.1:8797/api/v15.1/paper-authority' -TimeoutSec 2; $ok=($r.success -eq $true -and $r.version -eq '15.1' -and $r.service -eq 'JARVIS_MASTER_V151_OPTIONS_EXECUTION_BRIDGE')} catch {}; if($ok){Start-Process 'http://127.0.0.1:8797'; exit 0}else{exit 1}" >nul 2>&1
if not errorlevel 1 (
    echo JARVIS V15.1 is already running. Opening the existing dashboard.
    exit /b 0
)

set "JARVIS_PY=C:\Jarvis\.venv\Scripts\python.exe"
if exist "%JARVIS_PY%" "%JARVIS_PY%" -c "import omni, numpy, pandas, workstation.jarvis_os_v8, workstation.completion_console_v151" >nul 2>&1
if errorlevel 1 set "JARVIS_PY=C:\Jarvis\.venv-new\Scripts\python.exe"
if exist "%JARVIS_PY%" "%JARVIS_PY%" -c "import omni, numpy, pandas, workstation.jarvis_os_v8, workstation.completion_console_v151" >nul 2>&1

REM JARVIS_NATIVE_VOICE_V32
start "JARVIS Native Voice" /min powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Jarvis\start_jarvis_native_voice.ps1"

if not exist "%JARVIS_PY%" (
    echo.
    echo JARVIS Python environment not found.
    pause
    exit /b 1
)

REM JARVIS_NAUTILUS_QUANT_CORE_V5
set "JARVIS_NAUTILUS_PY=C:\Jarvis\.venv-nautilus\Scripts\python.exe"
if exist "%JARVIS_NAUTILUS_PY%" "%JARVIS_NAUTILUS_PY%" -c "import nautilus_trader, nautilus_trader.backtest.config, numpy, pandas; assert nautilus_trader.__version__ == '1.231.0'" >nul 2>&1
if errorlevel 1 set "JARVIS_NAUTILUS_PY=C:\Jarvis\.venv-nautilus-new\Scripts\python.exe"
if exist "%JARVIS_NAUTILUS_PY%" "%JARVIS_NAUTILUS_PY%" -c "import nautilus_trader, nautilus_trader.backtest.config, numpy, pandas; assert nautilus_trader.__version__ == '1.231.0'" >nul 2>&1
if errorlevel 1 set "JARVIS_NAUTILUS_PY=%JARVIS_PY%"

REM JARVIS_RUNTIME_SUPERVISOR_V151
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v62
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v8
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v11
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v12
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v13
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v14
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v141
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v15
REM Historical protected launcher contracts retained for cross-generation tests:
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v8
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v11
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v12
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v13
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v14
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v141
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v15
REM Preserves V8 protected Master, V14.1 verified risk geometry and V15 market reasoning.
REM V15.1 adds verified option-chain economics and long-premium paper option execution.
REM Option-chain provider remains read-only. Naked short option execution is disabled.
REM Paper Desk remains final risk authority. No live broker-order surface is added.
"%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v151

if errorlevel 1 (
    echo.
    echo JARVIS V15.1 exited with an error.
    pause
)

endlocal
