@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ============================================================
echo  SN 추출 테스트
echo ============================================================
echo.

python --version > nul 2>&1
if errorlevel 1 (
    echo [오류] Python을 찾을 수 없습니다.
    pause
    exit /b 1
)

python -c "import openpyxl" > nul 2>&1
if errorlevel 1 (
    echo [설치] openpyxl 설치 중...
    pip install openpyxl
)

echo.
if "%~1"=="" (
    echo CSV_DOWNLOAD_PATH 폴더에서 최신 xlsx 자동 탐색...
    python test_sn_extract.py
) else (
    echo 파일: %~1
    python test_sn_extract.py "%~1"
)

echo.
pause
