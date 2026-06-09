@echo off
cd /d "%~dp0"
echo ============================================================
echo   FA Service - Remove Auto-Start (Task Scheduler)
echo ============================================================
echo.

set TASK_NAME=FA-Service-Chatbot

schtasks /delete /tn "%TASK_NAME%" /f

if %errorlevel% == 0 (
    echo.
    echo [OK] Auto-start removed.
) else (
    echo.
    echo [FAIL] Task not found or need administrator privileges.
    echo        Please right-click and "Run as administrator".
)

echo.
pause
