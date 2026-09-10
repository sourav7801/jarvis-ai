@echo off
setlocal
cd /d "%~dp0"
title JARVIS Professional Paper Terminal
set "JARVIS_NO_BROWSER=0"
set "JARVIS_AUTO_PAPER_START=0"
set "JARVIS_V12_AUTO_PAPER_START=0"
powershell.exe -NoProfile -Command "$ok=$false; try {$r=Invoke-RestMethod 'http://127.0.0.1:8787/api/terminal/health' -TimeoutSec 2; $ok=($r.service -eq 'JARVIS_PROFESSIONAL_PAPER_TERMINAL')} catch {}; if($ok){Start-Process 'http://127.0.0.1:8787'; exit 0}else{exit 1}" >nul 2>&1
if not errorlevel 1 exit /b 0
set "JARVIS_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%JARVIS_PY%" set "JARVIS_PY=%~dp0.venv-new\Scripts\python.exe"
if not exist "%JARVIS_PY%" (
    echo JARVIS Python environment missing. See docs\PROFESSIONAL_TERMINAL.md.
    pause
    exit /b 1
)
"%JARVIS_PY%" "%~dp0start_jarvis_quant_terminal.py"
if errorlevel 1 pause
endlocal
