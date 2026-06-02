@echo off
chcp 65001 > nul
title FA Pipeline - Mail Download + Query

echo ============================================================
echo   FA Pipeline - Mail Download + SN Query
echo ============================================================
echo.

cd /d "%~dp0.."
python scripts\run_pipeline.py

echo.
pause
