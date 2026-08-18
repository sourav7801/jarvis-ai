@echo off
setlocal

cd /d C:\Jarvis

title JARVIS OS V3.1

if not exist "C:\Jarvis\.venv\Scripts\python.exe" (
    echo.
    echo JARVIS Python environment not found.
    pause
    exit /b 1
)

"C:\Jarvis\.venv\Scripts\python.exe" ^
"C:\Jarvis\start_jarvis_v3.py"

if errorlevel 1 (
    echo.
    echo JARVIS OS V3.1 exited with an error.
    pause
)

endlocal
