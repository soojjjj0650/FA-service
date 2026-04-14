@echo off
echo ==============================
echo  API 탐색: 10.246.56.50:8000
echo ==============================
echo.

echo [1] 기본 GET 요청...
curl -s -v http://10.246.56.50:8000
echo.
echo ------------------------------

echo [2] FastAPI 문서 확인...
curl -s http://10.246.56.50:8000/docs
echo.
echo ------------------------------

echo [3] OpenAPI JSON 스펙 확인...
curl -s http://10.246.56.50:8000/openapi.json
echo.
echo ------------------------------

echo [4] POST 테스트 (JSON)...
curl -s -X POST http://10.246.56.50:8000 -H "Content-Type: application/json" -d "{\"input\": \"test\"}"
echo.
echo ------------------------------

echo.
echo 완료. 위 결과를 복사해서 알려주세요.
pause
