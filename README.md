# FA 챗봇 서비스

FA(외부)가 단말기 **SN**을 입력하면, 내부 SQL 포털에서 데이터를 조회하고 AI Agent가 분석한 결과를 챗봇으로 반환하는 서비스입니다.

## 아키텍처

```
FA 사용자
    │ SN 입력
    ▼
챗봇 UI (WebSocket)
    │
    ▼
FastAPI 서버 (app/main.py)
    │
    ├─► Browser Pool (최대 5개 동시 실행)
    │       │ Playwright 브라우저 컨텍스트
    │       ▼
    │   Session Manager (로그인 1회, 세션 재사용)
    │       │
    │       ▼
    │   Query Runner (웹 스크래핑으로 SQL 실행, 5~15분)
    │       │
    ├─► Data Processor (결과 가공 → AI 프롬프트 생성)
    │
    └─► AI Agent Client (내부 AI Agent API 호출)
            │
            ▼
        챗봇 결과 반환
```

## 핵심 기능

| 기능 | 설명 |
|------|------|
| **세션 재사용** | 포털 로그인은 최초 1회만 수행, 이후 저장된 세션(쿠키) 재사용 |
| **5개 동시 실행** | `asyncio.Semaphore`로 최대 5개 브라우저 동시 실행 제어 |
| **실시간 진행 상태** | WebSocket으로 쿼리 진행 상태를 FA에게 실시간 전달 |
| **자동 재로그인** | 세션 만료 감지 시 자동 재로그인 후 재시도 |

## 설치 및 실행

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. Playwright 브라우저 설치
playwright install chromium

# 3. 환경 변수 설정
cp .env.example .env
# .env 파일에서 포털 URL, 계정 정보, AI Agent URL 수정

# 4. 서버 실행
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

브라우저에서 `http://localhost:8000` 접속

## 포털 적용 필수 수정 사항

실제 내부 포털에 맞게 다음 파일의 CSS selector를 수정해야 합니다.

### 1. 로그인 폼 (`app/scraper/session_manager.py`)

```python
# _fill_login_form() 메서드 수정
await page.fill('input[name="username"]', ...)  # 실제 username input selector
await page.fill('input[name="password"]', ...)  # 실제 password input selector
await page.click('button[type="submit"]')        # 실제 로그인 버튼 selector
```

### 2. SQL 에디터 및 실행 버튼 (`app/scraper/query_runner.py`)

```python
# _input_query(): SQL 입력 영역 selector
editor_selector = 'textarea#sql-editor'  # 실제 에디터 selector

# _submit_and_wait(): 실행 버튼 + 결과 테이블 selector
await page.click('button#run-query')                    # 실행 버튼
await page.wait_for_selector('.result-table', ...)      # 결과 테이블
```

### 3. SQL 쿼리 템플릿 (`app/scraper/query_runner.py`)

```python
SQL_TEMPLATE = """
    SELECT ... FROM devices WHERE serial_number = '{sn}'
"""
```

### 4. AI Agent 응답 파싱 (`app/agent/agent_client.py`)

```python
result = data.get("result")  # 실제 AI Agent 응답 JSON 키로 변경
```

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `PORTAL_URL` | 내부 SQL 포털 URL | - |
| `PORTAL_USERNAME` | 포털 로그인 아이디 | - |
| `PORTAL_PASSWORD` | 포털 로그인 비밀번호 | - |
| `AI_AGENT_URL` | 내부 AI Agent API URL | - |
| `MAX_CONCURRENT_BROWSERS` | 동시 브라우저 수 | 5 |
| `QUERY_TIMEOUT_SECONDS` | 쿼리 타임아웃(초) | 1200 |
| `BROWSER_HEADLESS` | 헤드리스 모드 여부 | true |

## API 엔드포인트

| 엔드포인트 | 설명 |
|-----------|------|
| `GET /` | 챗봇 UI |
| `WS /ws/chat` | WebSocket 챗봇 (권장) |
| `POST /api/query` | REST API 조회 |
| `GET /api/status` | 브라우저 풀 상태 |
| `POST /api/session/reset` | 세션 수동 초기화 |
