@echo off
chcp 65001 > nul
title FA Service - 초기 설치

echo ============================================================
echo   FA Service - 초기 설치 (최초 1회만 실행)
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/3] Python 패키지 설치 중...
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [오류] pip install 실패. Python이 설치되어 있는지 확인하세요.
    pause
    exit /b 1
)

echo.
echo [2/3] Playwright 브라우저 설치 중...
playwright install chromium
if errorlevel 1 (
    echo.
    echo [오류] playwright install 실패.
    pause
    exit /b 1
)

echo.
echo [3/3] 설치 완료!
echo.
echo ============================================================
echo   이제 사용 순서:
echo   1. login.bat         - 최초 로그인 (세션 저장)
echo   2. start_service.bat - 서비스 시작
echo ============================================================
echo.
pause
