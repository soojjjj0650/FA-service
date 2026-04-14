@echo off
echo ==============================
echo  API 엔드포인트 목록 확인
echo  http://10.246.56.50:8000
echo ==============================
echo.

curl -s http://10.246.56.50:8000/openapi.json | python -c "import json,sys; d=json.load(sys.stdin); [print(m.upper(), p) for p,v in d['paths'].items() for m in v]"

echo.
echo 위 목록을 복사해서 알려주세요.
pause
