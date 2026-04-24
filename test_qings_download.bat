@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ============================================================
echo  Qings 엑셀 다운로드 테스트
echo ============================================================
echo.

:: Python 확인
python --version > nul 2>&1
if errorlevel 1 (
    echo [오류] Python을 찾을 수 없습니다. Python이 설치되어 있는지 확인하세요.
    pause
    exit /b 1
)

:: Playwright 설치 확인 및 브라우저 설치
echo [1/2] Playwright 브라우저 확인 중...
python -m playwright install chromium > nul 2>&1
if errorlevel 1 (
    echo [오류] Playwright 설치에 문제가 있습니다.
    echo       pip install playwright 를 먼저 실행하세요.
    pause
    exit /b 1
)
echo       완료.
echo.

:: 테스트 실행
echo [2/2] Qings 다운로드 테스트 실행 중...
echo.
python test_qings_download.py
if errorlevel 1 (
    echo.
    echo [오류] 테스트 실행 중 오류가 발생했습니다. 위의 로그를 확인하세요.
)

echo.
pause
