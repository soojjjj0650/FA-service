@echo off
chcp 65001 > nul
title FA Service - 로그인

echo ============================================================
echo   FA Service - Superset 로그인 (최초 1회 / 세션 만료 시)
echo ============================================================
echo.

cd /d "%~dp0"
set PYTHONPATH=%~dp0
python scripts/manual_login.py

echo.
pause
