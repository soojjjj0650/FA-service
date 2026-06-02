@echo off
chcp 65001 > nul
title [2단계] FA 미결건 SN 쿼리 실행

echo ============================================================
echo   [2단계] 저장된 엑셀에서 SN 읽어 Superset 쿼리 실행
echo   탐색 경로: D:\FA_Service\userdata\FAdata
echo   결과 저장: D:\FA_Service\userdata
echo ============================================================
echo.

cd /d "%~dp0"

python --version > nul 2>&1
if errorlevel 1 (
    echo [오류] Python을 찾을 수 없습니다.
    pause
    exit /b 1
)

python run_batch.py %*

echo.
pause
