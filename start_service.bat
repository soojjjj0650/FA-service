@echo off
chcp 65001 > nul
title 통화품질 분석 서비스

echo ============================================================
echo   통화품질 분석 서비스
echo   챗봇 UI  : http://localhost:80
echo   배치 UI  : http://localhost:80/batch
echo ============================================================
echo.
echo   세션 미설정 시 login.bat 먼저 실행하세요.
echo   서버 종료: Ctrl+C
echo.

cd /d "%~dp0"
set "PYTHONPATH=%~dp0"
"C:\Users\sujin06.bae\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 80

echo.
echo 서버가 종료되었습니다.
pause
