@echo off
chcp 65001 > /dev/null
title Package Check
cd /d "%~dp0\.."
python -c "import fastapi; import playwright; import pyautogui; import pyperclip; print('OK - All packages ready')"
pause
