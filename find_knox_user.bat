@echo off
chcp 65001 > nul
title Knox User ID Search
cd /d "%~dp0"
python scripts\find_knox_user.py
