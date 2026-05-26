@echo off
chcp 65001 > nul
title FA Pending Mail Download

echo ============================================================
echo   FA 미결건 메일 첨부파일 다운로드
echo ============================================================
echo.

cd /d "%~dp0"
python scripts\run_mail_download.py

echo.
pause > nul
