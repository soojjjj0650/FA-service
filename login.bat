@echo off
chcp 65001 > nul
title FA Service - 로그인

echo ============================================================
echo   FA Service - Superset 로그인 (최초 1회 / 세션 만료 시)
echo ============================================================
echo.

cd /d "%~dp0"
py -3.12 scripts/manual_login.py

if errorlevel 1 (
    echo.
    echo [오류] 로그인 실패. 다시 시도해 주세요.
    pause
    exit /b 1
)

echo.
echo 로그인 완료! FA Service 서버를 시작합니다...
echo 브라우저에서 http://localhost:8000 으로 접속하세요.
echo 서버를 중지하려면 Ctrl+C 를 누르세요.
echo.

set "PYTHONPATH=%~dp0"
py -3.12 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

echo.
echo 서버가 종료되었습니다.
pause
