@echo off
chcp 65001 > nul
title Webhook 외부 테스트

echo ============================================================
echo   Webhook 외부 테스트 (다른 PC에서 실행)
echo   서버 IP를 입력하세요.
echo ============================================================
echo.

set /p SERVER_IP="서버 IP 입력 (예: 192.168.1.100): "

echo.
echo [1] 서버 연결 확인 중...
curl -s --max-time 5 http://%SERVER_IP%/docs > nul
if %errorlevel% neq 0 (
    echo    X 연결 실패 - 방화벽이 막혀 있거나 서버가 꺼져 있습니다.
    echo.
    pause
    exit /b
)
echo    O 서버 연결 성공
echo.

echo [2] SN 조회 요청 테스트...
curl -s -X POST http://%SERVER_IP%/webhook ^
  -H "Content-Type: application/json" ^
  -d "{\"action\":\"search_sn\",\"sn_value\":\"TEST-001\"}"

echo.
echo.
echo 완료. 아무 키 누르세요.
pause > nul
