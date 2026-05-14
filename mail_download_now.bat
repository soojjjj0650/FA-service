@echo off
chcp 65001 > nul
title FA 미결건 메일 다운로드 (단독 실행)

echo ============================================================
echo   FA 미결건 메일 첨부파일 다운로드
echo ============================================================
echo.

cd /d "%~dp0"
python scripts\run_mail_download.py

echo.
pause > nul
