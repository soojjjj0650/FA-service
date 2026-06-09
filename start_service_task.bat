@echo off
chcp 65001 > nul
title FA Service

cd /d "%~dp0"
set "PYTHONPATH=%~dp0"
"C:\Users\sujin06.bae\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 80
