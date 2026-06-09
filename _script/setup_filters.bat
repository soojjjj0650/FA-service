@echo off
chcp 65001 > nul
cd /d "%~dp0\.."

python -c "import openpyxl" > nul 2>&1
if errorlevel 1 (
    python -m pip install openpyxl
)

python setup_filters.py
