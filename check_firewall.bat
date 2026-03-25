@echo off
chcp 65001 > nul
title Windows 방화벽 포트 80 확인

echo ============================================================
echo   Windows 방화벽 포트 80 인바운드 규칙 확인
echo ============================================================
echo.

netsh advfirewall firewall show rule dir=in name=all | findstr /C:"규칙 이름" /C:"동작" /C:"LocalPort"

echo.
echo 완료. 아무 키 누르세요.
pause > nul
