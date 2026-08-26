@echo off
setlocal
cd /d "%~dp0"

echo Starting the complete JARVIS V5 system...
echo Master dashboard: http://127.0.0.1:8797
echo Quant signal terminal: http://127.0.0.1:8787
echo Keep this window open. Press Ctrl+C here to stop Master JARVIS.
call "%~dp0JARVIS.bat"

if errorlevel 1 (
  echo.
  echo JARVIS stopped with an error. If port 8787 is already in use,
  echo close the older JARVIS terminal and run this launcher again.
  pause
)
