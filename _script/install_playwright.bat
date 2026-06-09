@echo off
chcp 65001 > /dev/null
title FA Service - Playwright Install

echo ============================================================
echo   Playwright Chromium 브라우저 설치
echo   (최초 1회만 실행하면 됩니다)
echo ============================================================
echo.

cd /d "%~dp0\.."
"C:\Users\sujin06.bae\AppData\Local\Programs\Python\Python312\python.exe" -m playwright install chromium

echo.
echo 설치 완료! 이제 test_pdf.bat 을 실행하세요.
echo.
pause
