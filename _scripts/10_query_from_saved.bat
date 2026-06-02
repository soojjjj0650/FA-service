@echo off
chcp 65001 > nul
title FA Query from Saved Excel

echo ============================================================
echo   FA Query Runner - Read SN from Excel, Run Superset Query
echo   Search: D:\FA_Service\userdata\FAdata
echo   Output: D:\FA_Service\userdata
echo ============================================================
echo.

cd /d "%~dp0.."

python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    pause
    exit /b 1
)

python run_batch.py %*

echo.
pause
