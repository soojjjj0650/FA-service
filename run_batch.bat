@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ====================================================
echo  FA Service - Batch Query Runner
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

echo.
if "%~1"=="" goto auto
python run_batch.py "%~1"
goto done

:auto
python run_batch.py

:done
echo.
pause
