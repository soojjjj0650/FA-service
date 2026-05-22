@echo off
cd /d "%~dp0"
set "PYTHON=C:\Users\sujin06.bae\AppData\Local\Programs\Python\Python312\python.exe"
set "USERDATA=%~dp0userdata"
set "OUTDIR=%~dp0test\output"

echo.
echo ============================
echo  FA Analysis - PDF Generator
echo ============================
echo.

set /p SN=SN:
if "%SN%"=="" (
    echo No SN entered.
    pause
    exit /b
)

set "CSV=%USERDATA%\%SN%_inputdata.csv"
if not exist "%CSV%" (
    echo File not found: %CSV%
    pause
    exit /b
)

echo.
echo Processing: %CSV%
echo.

"%PYTHON%" test\test_excel_to_pdf.py "%CSV%" "%SN%"

set "PDF=%OUTDIR%\%SN%_analysis.pdf"
if exist "%PDF%" (
    echo.
    echo Opening PDF...
    start "" "%PDF%"
)

echo.
pause
