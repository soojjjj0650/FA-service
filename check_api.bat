@echo off
echo ==============================
echo  API 엔드포인트 목록 확인
echo  http://10.246.56.50:8000
echo ==============================
echo.

echo [1] 전체 엔드포인트 목록...
curl -s http://10.246.56.50:8000/openapi.json | python -c "import json,sys; d=json.load(sys.stdin); [print(m.upper(), p) for p,v in d['paths'].items() for m in v]"

echo.
echo ------------------------------
echo [2] FA 관련 엔드포인트 상세...
curl -s http://10.246.56.50:8000/openapi.json | python -c "import json,sys; d=json.load(sys.stdin); p=d['paths']; [print(json.dumps(v, indent=2, ensure_ascii=False)) for path,v in p.items() if 'fa' in path.lower()]"

echo.
echo 위 결과를 복사해서 알려주세요.
pause
