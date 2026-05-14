@echo off
chcp 65001 > nul
title FA 메일 다운로드 이력 초기화
cd /d "%~dp0"
python scripts\run_mail_download.py --reset
