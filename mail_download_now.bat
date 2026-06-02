@echo off
chcp 65001 > nul
title [1단계] FA 미결건 메일 다운로드

echo ============================================================
echo   [1단계] FA 미결건 메일 첨부파일 다운로드
echo   samsung.net 메일 → D:\FA_Service\userdata\FAdata 저장
echo ============================================================
echo.

cd /d "%~dp0"
python scripts\run_mail_download.py

echo.
pause
