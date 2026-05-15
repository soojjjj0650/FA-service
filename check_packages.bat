@echo off
chcp 65001 > nul
title 패키지 확인
cd /d "%~dp0"
python -c "import fastapi; import playwright; import pyautogui; import pyperclip; print('OK - 모든 패키지 정상')"
pause
