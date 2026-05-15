@echo off
chcp 65001 > nul
title FA 전체 파이프라인 (메일 다운로드 + 쿼리 실행)
cd /d "%~dp0"
python scripts\run_pipeline.py
