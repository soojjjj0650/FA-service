@echo off
chcp 65001 > nul
title FA Service - PDF 생성

cd /d "%~dp0"
set "PYTHONPATH=%~dp0"
set "PYTHON=C:\Users\sujin06.bae\AppData\Local\Programs\Python\Python312\python.exe"
set "USERDATA=%~dp0userdata"

:input
echo.
echo ============================================================
echo   FA 분석 PDF 생성
echo ============================================================
echo.
set /p "SN=SN 번호 입력 (예: R3CW804XAD): "
if "%SN%"=="" goto input

set "CSV=%USERDATA%\%SN%_inputdata.csv"
if not exist "%CSV%" (
    echo.
    echo [오류] 파일 없음: %CSV%
    echo.
    pause
    goto input
)

echo.
echo 처리 중... %CSV%
echo.

"%PYTHON%" test\test_excel_to_pdf.py "%CSV%" "%SN%"

set "PDF=%~dp0test\output\%SN%_analysis.pdf"
if exist "%PDF%" (
    echo.
    echo PDF 열기 중...
    start "" "%PDF%"
)

echo.
pause
