@echo off
chcp 65001 > nul
title Data Processor Test

echo ================================================================
echo   Data Processor 단독 테스트
echo ----------------------------------------------------------------
echo   인자 없음  : CSV_DOWNLOAD_PATH 내 최신 CSV 자동 사용
echo   인자 = SN  : 해당 SN CSV 파일 탐색  (예: R3CR3019MEF)
echo   인자 = 경로: 해당 CSV 파일 직접 사용
echo ================================================================
echo.

cd /d "%~dp0"
set "PYTHONPATH=%~dp0"
set "PYTHON=C:\Users\sujin06.bae\AppData\Local\Programs\Python\Python312\python.exe"

if "%~1"=="" (
    "%PYTHON%" scripts/test_data_processor.py
) else (
    "%PYTHON%" scripts/test_data_processor.py %1
)

echo.
pause
