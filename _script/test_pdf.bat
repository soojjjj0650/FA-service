@echo off
chcp 65001 > nul
title FA Service - PDF Test

echo ============================================================
echo   FA Service - PDF 생성 테스트
echo ============================================================
echo.

cd /d "%~dp0\.."
set "PYTHONPATH=%~dp0\.."
"C:\Users\sujin06.bae\AppData\Local\Programs\Python\Python312\python.exe" test/test_pdf.py

echo.
pause
