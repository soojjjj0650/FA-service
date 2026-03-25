@echo off
chcp 65001 > nul
title Webhook 외부 테스트

echo ============================================================
echo   Webhook 외부 테스트 (다른 PC에서 실행)
echo ============================================================
echo.
set /p SERVER_IP="서버 IP 입력 (예: 192.168.1.100): "
echo.
echo [1] 연결 테스트 중...
echo.

powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://%SERVER_IP%/webhook' -Method POST -ContentType 'application/json' -Body '{\"action\":\"search_sn\",\"sn_value\":\"TEST-001\"}' -UseBasicParsing; Write-Host '상태코드:' $r.StatusCode; Write-Host '응답내용:' $r.Content } catch { Write-Host '오류:' $_.Exception.Message }"

echo.
echo 완료. 아무 키 누르세요.
pause > nul
