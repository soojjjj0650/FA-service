@echo off
chcp 65001 > nul
title FA Service - Session Refresh

echo ====================================================
echo  FA Service - Superset Login Session Refresh
echo ====================================================
echo.
echo  Browser will open automatically.
echo  Please approve Bio authentication (fingerprint/Face ID) on your phone.
echo.

cd /d "%~dp0\.."
"C:\Users\sujin06.bae\AppData\Local\Programs\Python\Python312\python.exe" scripts/manual_login.py

if errorlevel 1 (
    echo.
    echo [ERROR] Login failed. Please try again manually.
    pause
    exit /b 1
)

echo.
echo  Session refresh complete!
timeout /t 3 > nul
