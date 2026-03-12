@echo off
chcp 65001 > nul
title FA Service - 실행 중

echo ============================================================
echo   FA Service 시작
echo   배치 쿼리 UI : http://localhost:8000/batch
echo   챗봇 UI      : http://localhost:8000
echo ============================================================
echo.
echo   세션이 없으면 먼저 login.bat 을 실행하세요.
echo   서버를 중지하려면 이 창에서 Ctrl+C 를 누르세요.
echo.

cd /d "%~dp0"
set "PYTHONPATH=%~dp0"
"C:\Users\sujin06.bae\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000

echo.
echo 서버가 종료되었습니다.
pause
