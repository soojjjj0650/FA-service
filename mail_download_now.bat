@echo off
chcp 65001 > nul
title FA Mail Download

echo ============================================================
echo   FA Mail Attachment Download
echo   samsung.net -^> D:\FA_Service\userdata\FAdata
echo ============================================================
echo.

cd /d "%~dp0"
python scripts\run_mail_download.py

echo.
pause
