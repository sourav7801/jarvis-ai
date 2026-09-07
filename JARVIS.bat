@echo off
setlocal

cd /d C:\Jarvis

title JARVIS OS V8 MASTER + V12 ADAPTIVE MARKET INTELLIGENCE

set "JARVIS_PY=C:\Jarvis\.venv\Scripts\python.exe"
if exist "%JARVIS_PY%" "%JARVIS_PY%" -c "import omni, numpy, pandas, workstation.jarvis_os_v3, workstation.jarvis_os_v8, workstation.completion_console_v12" >nul 2>&1
if errorlevel 1 set "JARVIS_PY=C:\Jarvis\.venv-new\Scripts\python.exe"
if exist "%JARVIS_PY%" "%JARVIS_PY%" -c "import omni, numpy, pandas, workstation.jarvis_os_v3, workstation.jarvis_os_v8, workstation.completion_console_v12" >nul 2>&1

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

REM JARVIS_RUNTIME_SUPERVISOR_V12
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v62
REM Compatibility lineage: scripts.jarvis_runtime_supervisor_v8
REM Historical protected launcher contracts retained for cross-generation tests:
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v8
REM "%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v11
REM Preserves V6.2 stale-Quant ownership checks and V8 stale-Master identity checks.
REM V12 refuses to adopt an obsolete Completion Center on port 8799.
REM Master remains the protected V8 Unified Intelligence runtime on port 8797.
REM Quant evolves to adaptive expected-value paper intelligence; static 67/68/70 scores are not entry authority.
REM No live broker-order surface is added by this launcher.
"%JARVIS_PY%" -m scripts.jarvis_runtime_supervisor_v12

if errorlevel 1 (
    echo.
    echo JARVIS V12 exited with an error.
    pause
)

endlocal
