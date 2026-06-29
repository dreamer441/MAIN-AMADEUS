@echo off
setlocal

rem AMADEUS V2 Core launcher for Windows.
rem Keeps the window open after Core exits so startup logs stay visible.

cd /d "%~dp0"

echo Starting AMADEUS V2 Core...
echo.

py -3 main.py

echo.
if errorlevel 1 (
    echo AMADEUS Core exited with an error.
) else (
    echo AMADEUS Core exited normally.
)

echo.
pause
