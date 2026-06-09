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
echo ==============================
echo  GET API 응답 확인
echo ==============================
echo.

echo [3] GET /api/weeks
curl -s http://10.246.56.50:8000/api/weeks
echo.
echo ------------------------------

echo [4] GET /api/stations
curl -s http://10.246.56.50:8000/api/stations
echo.
echo ------------------------------

echo [5] GET /api/stats
curl -s http://10.246.56.50:8000/api/stats
echo.
echo ------------------------------

echo [6] GET /api/fa-data
curl -s http://10.246.56.50:8000/api/fa-data
echo.
echo ------------------------------

echo [7] GET /api/repeter-data
curl -s http://10.246.56.50:8000/api/repeter-data
echo.
echo ------------------------------

echo [8] GET /api/tau-reject-data
curl -s http://10.246.56.50:8000/api/tau-reject-data
echo.
echo ------------------------------

echo [9] GET /api/pci-duplicates
curl -s http://10.246.56.50:8000/api/pci-duplicates
echo.
echo ------------------------------

echo [10] GET /api/improvement
curl -s http://10.246.56.50:8000/api/improvement
echo.
echo ------------------------------

echo.
echo ==============================
echo  서버측 필터링 테스트
echo ==============================
echo.

echo [11] 쿼리 파라미터 필터링 테스트 (operator+TAC+PCI)
curl -s "http://10.246.56.50:8000/api/stations?operator=SKT&tac=18469&pci=160"
echo.

echo.
echo ==============================
echo  operator 고유값 확인
echo ==============================
echo.

echo [12] API내 operator 값 목록
curl -s http://10.246.56.50:8000/api/stations | python -c "import json,sys; d=json.load(sys.stdin); ops=set(x.get('operator','') for x in d); print(sorted(ops))"
echo.

echo.
echo ==============================
echo  operator별 필터링 테스트
echo ==============================
echo.

echo [13] ?operator=KT
curl -s "http://10.246.56.50:8000/api/stations?operator=KT" | python -c "import json,sys; d=json.load(sys.stdin); print(type(d), len(d) if isinstance(d,list) else d)"
echo.

echo [14] ?operator=LGU
curl -s "http://10.246.56.50:8000/api/stations?operator=LGU" | python -c "import json,sys; d=json.load(sys.stdin); print(type(d), len(d) if isinstance(d,list) else d)"
echo.

echo [15] ?operator=SKT (비교용)
curl -s "http://10.246.56.50:8000/api/stations?operator=SKT" | python -c "import json,sys; d=json.load(sys.stdin); print(type(d), len(d) if isinstance(d,list) else d)"
echo.

echo [16] ?operator=KT 응답의 operator 고유값 확인
curl -s "http://10.246.56.50:8000/api/stations?operator=KT" | python -c "import json,sys; d=json.load(sys.stdin); ops=set(x.get('operator','') for x in d); print(sorted(ops)[:10])"
echo.

echo.
echo 완료. 위 결과를 복사해서 알려주세요.
pause
