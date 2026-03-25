@echo off
chcp 65001 > nul
title Webhook 로컬 테스트

echo ============================================================
echo   Webhook 로컬 테스트 (서버 PC에서 실행)
echo ============================================================
echo.
echo [1] SN 조회 요청 테스트 중...
echo.

powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8000/webhook' -Method POST -ContentType 'application/json' -Body '{\"action\":\"search_sn\",\"sn_value\":\"TEST-001\"}' -UseBasicParsing; Write-Host '상태코드:' $r.StatusCode; Write-Host '응답내용:' $r.Content } catch { Write-Host '오류:' $_.Exception.Message }"

echo.
echo 완료. 아무 키 누르세요.
pause > nul
