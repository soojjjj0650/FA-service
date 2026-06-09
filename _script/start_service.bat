@echo off
chcp 65001 > nul
title FA Service

echo ============================================================
echo   FA Service
echo   Chatbot UI  : http://localhost:80
echo   Batch UI    : http://localhost:80/batch
echo ============================================================
echo.
echo   Run login.bat first if session is not set.
echo   Press Ctrl+C to stop the server.
echo.

cd /d "%~dp0\.."
set "PYTHONPATH=%~dp0\.."
"C:\Users\sujin06.bae\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 80

echo.
echo Server stopped.
pause
