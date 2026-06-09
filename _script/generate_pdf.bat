@echo off
cd /d "%~dp0\.."
set "PYTHON=C:\Users\sujin06.bae\AppData\Local\Programs\Python\Python312\python.exe"
set "USERDATA=%~dp0\..\userdata"
set "OUTDIR=%~dp0\..\test\output"

echo.
echo ============================
echo  FA Analysis - Report Generator
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
echo 1. PDF
echo 2. ZIP (HTML)
echo.
set /p MODE=Select (1/2):
if "%MODE%"=="2" goto make_zip

:make_pdf
echo.
echo Generating PDF...
"%PYTHON%" test\test_excel_to_pdf.py "%CSV%" "%SN%"
set "OUT=%OUTDIR%\%SN%_analysis.pdf"
goto open_file

:make_zip
echo.
echo Generating ZIP...
"%PYTHON%" test\test_excel_to_pdf.py "%CSV%" "%SN%" --zip
set "OUT=%OUTDIR%\%SN%_analysis.zip"

:open_file
if exist "%OUT%" (
    echo.
    start "" "%OUT%"
)

echo.
pause
