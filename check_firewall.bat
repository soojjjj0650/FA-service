@echo off
chcp 65001 > nul
title Windows 방화벽 포트 80 확인

echo ============================================================
echo   Windows 방화벽 포트 80 인바운드 규칙 확인
echo ============================================================
echo.

powershell -Command "Get-NetFirewallRule -Direction Inbound | Where-Object { $_.Enabled -eq 'True' } | ForEach-Object { $p = $_ | Get-NetFirewallPortFilter; if ($p.LocalPort -eq '80' -or $p.LocalPort -eq 'Any') { Write-Host ('규칙: ' + $_.DisplayName + ' | 동작: ' + $_.Action + ' | 포트: ' + $p.LocalPort) } }"

echo.
echo 완료. 아무 키 누르세요.
pause > nul
