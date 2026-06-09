@echo off
chcp 65001 > nul
title FA Mail Download History Reset
cd /d "%~dp0\.."
python scripts\run_mail_download.py --reset
