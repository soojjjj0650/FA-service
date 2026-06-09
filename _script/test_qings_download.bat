@echo off
chcp 65001 > nul
cd /d "%~dp0\.."

echo ============================================================
echo  Qings 엑셀 다운로드 테스트
echo ============================================================
echo.

:: Python 확인
python --version > nul 2>&1
if errorlevel 1 (
    echo [오류] Python을 찾을 수 없습니다.
    pause
    exit /b 1
)

:: Playwright 패키지 확인
echo [1/3] Playwright 패키지 확인...
python -c "import playwright" > nul 2>&1
if errorlevel 1 (
    echo       설치 중...
    pip install playwright
)
echo       완료.
echo.

:: Playwright 브라우저 설치 (출력 보이게)
echo [2/3] Playwright Chromium 브라우저 설치 중...
python -m playwright install chromium
if errorlevel 1 (
    echo.
    echo [오류] Chromium 설치 실패.
    pause
    exit /b 1
)
echo       완료.
echo.

:: 테스트 실행
echo [3/3] Qings 다운로드 테스트 실행...
echo.
python test_qings_download.py

echo.
pause
