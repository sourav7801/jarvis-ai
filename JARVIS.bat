@echo off
setlocal

cd /d C:\Jarvis

title JARVIS OS V5

set "JARVIS_PY=C:\Jarvis\.venv\Scripts\python.exe"
if exist "%JARVIS_PY%" "%JARVIS_PY%" -c "import omni, numpy, pandas, workstation.jarvis_os_v3" >nul 2>&1
if errorlevel 1 set "JARVIS_PY=C:\Jarvis\.venv-new\Scripts\python.exe"
if exist "%JARVIS_PY%" "%JARVIS_PY%" -c "import omni, numpy, pandas, workstation.jarvis_os_v3" >nul 2>&1

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
if exist "%JARVIS_NAUTILUS_PY%" (
    start "JARVIS Nautilus Quant Core" /min "%JARVIS_NAUTILUS_PY%" "C:\Jarvis\start_jarvis_nautilus_core.py"
) else (
    start "JARVIS Nautilus Quant Core" /min "%JARVIS_PY%" "C:\Jarvis\start_jarvis_nautilus_core.py"
)

REM JARVIS_QUANT_TRADING_INTELLIGENCE_V1
start "JARVIS Quant Trading Intelligence" /min "%JARVIS_PY%" "C:\Jarvis\start_jarvis_quant_terminal.py"

"%JARVIS_PY%" ^
"C:\Jarvis\start_jarvis_v3.py"

if errorlevel 1 (
    echo.
    echo JARVIS OS V5 exited with an error.
    pause
)

endlocal
