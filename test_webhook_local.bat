@echo off
chcp 65001 > nul
title Webhook 로컬 테스트

echo ============================================================
echo   Webhook 로컬 테스트 (서버 PC에서 실행)
echo ============================================================
echo.

echo [1] SN 조회 요청 테스트...
curl -s -X POST http://localhost/webhook ^
  -H "Content-Type: application/json" ^
  -d "{\"action\":\"search_sn\",\"sn_value\":\"TEST-001\"}"

echo.
echo.
echo [2] 응답 위 결과 확인 후 아무 키 누르세요.
pause > nul
