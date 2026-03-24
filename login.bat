@echo off
chcp 65001 > nul
title FA Service - Login

echo ============================================================
echo   FA Service Login
echo   (First time setup or session expired)
echo ============================================================
echo.

cd /d "%~dp0"
"C:\Users\sujin06.bae\AppData\Local\Programs\Python\Python312\python.exe" scripts/manual_login.py

if errorlevel 1 (
    echo.
    echo [ERROR] Login failed. Please try again.
    pause
    exit /b 1
)

echo.
echo Login complete! Starting FA Service server...
echo Open browser: http://localhost:80
echo Press Ctrl+C to stop the server.
echo.

set "PYTHONPATH=%~dp0"
"C:\Users\sujin06.bae\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 80

echo.
echo Server stopped.
pause
