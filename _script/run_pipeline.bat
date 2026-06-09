@echo off
chcp 65001 > nul
title FA Pipeline - Mail Download + Query
cd /d "%~dp0\.."
python scripts\run_pipeline.py
