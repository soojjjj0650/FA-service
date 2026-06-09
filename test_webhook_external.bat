@echo off
chcp 65001 > nul
title Webhook External Test

echo ============================================================
echo   Webhook 외부 테스트 (다른 PC에서 실행)
echo ============================================================
echo.
set /p SERVER_IP=Enter Server IP (e.g. 192.168.1.100):
echo.
echo [1] 연결 테스트 중...
echo.

powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://%SERVER_IP%/webhook' -Method POST -ContentType 'application/json' -Body '{\"action\":\"search_sn\",\"sn_value\":\"TEST-001\"}' -UseBasicParsing; Write-Host 'StatusCode:' $r.StatusCode; Write-Host 'Response:' $r.Content } catch { Write-Host 'Error:' $_.Exception.Message }"

echo.
echo 완료. 아무 키 누르세요.
pause > nul
