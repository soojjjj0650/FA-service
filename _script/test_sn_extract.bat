@echo off
chcp 65001 > nul
cd /d "%~dp0\.."

echo ====================================================
echo  FA Service - SN Extract Test
echo ====================================================
echo.

python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    pause
    exit /b 1
)

python -c "import openpyxl" > nul 2>&1
if errorlevel 1 (
    echo [INSTALL] Installing openpyxl...
    python -m pip install openpyxl
)

python -c "import xlrd" > nul 2>&1
if errorlevel 1 (
    echo [INSTALL] Installing xlrd...
    python -m pip install xlrd
)

echo.
if "%~1"=="" goto auto
python test_sn_extract.py "%~1"
goto done

:auto
python test_sn_extract.py

:done
echo.
pause
