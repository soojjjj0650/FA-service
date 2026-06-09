@echo off
chcp 65001 > /dev/null
title Knox User ID Search
cd /d "%~dp0\.."
python scripts\find_knox_user.py
