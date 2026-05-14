@echo off
chcp 65001 > nul
cd /d "%~dp0"
python scripts\reset_mail_ids.py
