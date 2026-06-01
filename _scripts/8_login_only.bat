@echo off
chcp 65001 > nul
title 통화품질 분석서비스 - 세션 갱신

echo ====================================================
echo  통화품질 분석서비스 - Superset 로그인 세션 갱신
echo ====================================================
echo.
echo  브라우저가 자동으로 열립니다.
echo  핸드폰에서 Bio 인증(지문/Face ID)을 승인해주세요.
echo.

cd /d "%~dp0\.."
"C:\Users\sujin06.bae\AppData\Local\Programs\Python\Python312\python.exe" scripts/manual_login.py

if errorlevel 1 (
    echo.
    echo [오류] 로그인 실패. 수동으로 다시 시도해주세요.
    pause
    exit /b 1
)

echo.
echo  세션 갱신 완료!
timeout /t 3 > nul
