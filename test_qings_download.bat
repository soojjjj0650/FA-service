@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ============================================================
echo  Qings 엑셀 다운로드 테스트
echo ============================================================
echo.

python test_qings_download.py

echo.
pause
