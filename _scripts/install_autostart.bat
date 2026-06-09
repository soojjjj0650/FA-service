@echo off
cd /d "%~dp0"
echo ============================================================
echo   FA Service - Register Auto-Start (Task Scheduler)
echo ============================================================
echo.

set TASK_NAME=FA-Service-Chatbot
set SCRIPT_PATH=%~dp0start_service_task.bat

echo Task Name : %TASK_NAME%
echo Script    : %SCRIPT_PATH%
echo Trigger   : At logon (minimized)
echo.

schtasks /create /tn "%TASK_NAME%" /tr "cmd /c start /min \"%SCRIPT_PATH%\"" /sc onlogon /rl highest /f

if %errorlevel% == 0 (
    echo.
    echo [OK] Auto-start registered. Service will start on next login.
    echo      To start now, run start_service.bat
) else (
    echo.
    echo [FAIL] Please right-click and "Run as administrator".
)

echo.
pause
