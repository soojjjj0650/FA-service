@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ============================================================
echo  SN ์ถ"์ถœ ํ…Œ์ŠคํŠธ
echo ============================================================
echo.

python --version > nul 2>&1
if errorlevel 1 (
    echo [์˜ค๋ฅ˜] Python์„ ์ฐพ์„ ์ˆ˜ ์—†์Šต๋‹ˆ๋‹ค.
    pause
    exit /b 1
)

python -c "import openpyxl" > nul 2>&1
if errorlevel 1 (
    echo [์„ค์น˜] openpyxl ์„ค์น˜ ์ค'...
    pip install openpyxl
)

python -c "import xlrd" > nul 2>&1
if errorlevel 1 (
    echo [์„ค์น˜] xlrd ์„ค์น˜ ์ค'...
    pip install xlrd
)

echo.
if "%~1"=="" goto auto
python test_sn_extract.py "%~1"
goto done

:auto
echo CSV_DOWNLOAD_PATH ํด๋"์—์„œ ์ตœ์‹  xls/xlsx ์ž๋™ ํƒ์ƒ‰...
python test_sn_extract.py

:done
echo.
pause
