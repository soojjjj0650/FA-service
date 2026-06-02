@echo off
chcp 65001 > nul
title Task Scheduler Registration

echo ====================================================
echo  Daily 9AM Auto Login Schedule Registration
echo ====================================================
echo.

:: Set path based on current script location
set "SCRIPT_DIR=%~dp0"
set "LOGIN_BAT=%SCRIPT_DIR%8_login_only.bat"

echo  Target batch file:
echo  %LOGIN_BAT%
echo.

:: Delete existing task (if any)
schtasks /delete /tn "FA_AutoLogin" /f > nul 2>&1

:: Register task scheduler: daily at 09:00
schtasks /create ^
  /tn "FA_AutoLogin" ^
  /tr "\"%LOGIN_BAT%\"" ^
  /sc daily ^
  /st 09:00 ^
  /ru "%USERNAME%" ^
  /rl limited ^
  /f

if errorlevel 1 (
    echo.
    echo [ERROR] Task scheduler registration failed.
    echo        Please run as administrator.
    pause
    exit /b 1
)

echo.
echo ====================================================
echo  Registration complete!
echo  Login window will open automatically at 09:00 every day.
echo  Just approve Bio authentication on your phone.
echo.
echo  To verify registered task:
echo  Open Task Scheduler - FA_AutoLogin
echo ====================================================
echo.
schtasks /query /tn "FA_AutoLogin" /fo list 2>nul
echo.
pause
