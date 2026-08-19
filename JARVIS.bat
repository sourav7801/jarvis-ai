@echo off
setlocal

cd /d C:\Jarvis

title JARVIS OS V3.2

REM JARVIS_NATIVE_VOICE_V32
start "JARVIS Native Voice" /min powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Jarvis\start_jarvis_native_voice.ps1"

if not exist "C:\Jarvis\.venv\Scripts\python.exe" (
    echo.
    echo JARVIS Python environment not found.
    pause
    exit /b 1
)

REM JARVIS_QUANT_TRADING_INTELLIGENCE_V1
start "JARVIS Quant Trading Intelligence" /min "C:\Jarvis\.venv\Scripts\python.exe" "C:\Jarvis\start_jarvis_quant_terminal.py"

"C:\Jarvis\.venv\Scripts\python.exe" ^
"C:\Jarvis\start_jarvis_v3.py"

if errorlevel 1 (
    echo.
    echo JARVIS OS V3.2 exited with an error.
    pause
)

endlocal
