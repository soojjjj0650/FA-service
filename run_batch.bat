@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ============================================================
echo  SN 배치 쿼리 실행
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
    python -m pip install openpyxl
)

echo.
if "%~1"=="" goto auto
python run_batch.py "%~1"
goto done

:auto
python run_batch.py

:done
echo.
pause
