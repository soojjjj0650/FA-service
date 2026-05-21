"""
FA Chatbot Service - Configuration
"""
from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    # ─── Superset SQL Lab (웹 스크래핑 대상) ────────────────────────────────
    PORTAL_URL: str = "https://superset-kr.bigdata.samsung.com/superset/sqllab"
    PORTAL_LOGIN_URL: str = "https://superset-kr.bigdata.samsung.com/superset/sqllab"
    PORTAL_QUERY_URL: str = "https://superset-kr.bigdata.samsung.com/superset/sqllab"

    PORTAL_USERNAME: str = "sujin06.bae"
    PORTAL_PASSWORD: str = "tnwls06!"

    # ─── Edge 브라우저 경로 (Windows) ────────────────────────────────────────
    EDGE_EXECUTABLE_PATH: str = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

    # ─── CSV 다운로드 경로 ────────────────────────────────────────────────────
    CSV_DOWNLOAD_PATH: str = r"C:\Users\sujin06.bae\Desktop\FA_Service_data\FA_Service\userdata"

    # ─── 세션 저장 경로 ──────────────────────────────────────────────────────
    SESSION_FILE: Path = BASE_DIR / "data" / "sessions" / "portal_session.json"

    # ─── 브라우저 풀 설정 ────────────────────────────────────────────────────
    MAX_CONCURRENT_BROWSERS: int = 5          # 동시 실행 브라우저 최대 수 (SN 최대 5개)
    BROWSER_HEADLESS: bool = False            # Edge는 headless=False 권장
    QUERY_TIMEOUT_SECONDS: int = 3600        # 쿼리 타임아웃 (최대 1시간)
    SESSION_REUSE: bool = True               # 세션 재사용 여부

    # ─── 내부 AI Agent ───────────────────────────────────────────────────────
    AI_AGENT_URL: str = "https://agent.sec.samsung.net/api/v1/run/f0bb8a7f-69c0-4343-8251-1483286bbb22?stream=false"
    AI_AGENT_API_KEY: str = "sk-TnJNxPXgqSMH9ikmNk5alN99JfkKy4CXQPDYqY_EWx8"
    AI_AGENT_INPUT_KEY: str = "TextInput-n8kcD"   # 실제 데이터 입력 컴포넌트 key
    # 프롬프트 템플릿 컴포넌트 key (비워두면 해당 component_input 미전송)
    # Langflow flow에서 prompt 컴포넌트의 key 값 입력 (예: "prompt-rFpiB")
    AI_AGENT_PROMPT_KEY: str = "prompt-rFpiB"
    # 프롬프트 템플릿 내용 (비워두면 Langflow flow 기본값 사용)
    AI_AGENT_PROMPT_TEMPLATE: str = ""
    AI_AGENT_TIMEOUT: int = 120
    # AI Agent 입력 포맷: "table" (표 형식) 또는 "narrative" (서술형)
    AI_AGENT_INPUT_FORMAT: str = "narrative"

    # ─── 회사 챗봇 웹훅 (FA 분석 완료 시 결과 push) ──────────────────────────
    CHATBOT_WEBHOOK_URL: str = "https://botbuilder.samsung.net/webhook/fa.service"
    # 분석 완료 후 채팅방으로 결과 카드를 push하는 URL
    # chatRoomId가 URL 끝에 자동으로 붙음: {CHATBOT_PUSH_URL}/{chatRoomId}
    # 예: https://botbuilder.samsung.net/webhook/fa.service
    CHATBOT_PUSH_URL: str = "https://botbuilder.samsung.net/webhook/fa.service"
    CHATBOT_PUSH_API_KEY: str = ""   # push API 인증 키 (필요 시)

    # ─── Knox Messenger / Teams API ──────────────────────────────────────────
    # 스테이지: https://openapi.stage.samsung.net  (IP: 203.254.214.131, Port: 80/443)
    # 운  영:  https://openapi.samsung.net         (IP: 112.107.220.134, Port: 80/443)
    KNOX_MESSENGER_BASE_URL: str = "https://openapi.stage.samsung.net"   # 스테이지 기본값
    KNOX_ACCESS_TOKEN: str = ""             # Bearer 토큰
    KNOX_SYSTEM_ID: str = "C60LD0001"       # System-ID
    KNOX_DEVICE_ID: str = ""               # x-device-id (미설정 시 자동 등록)
    KNOX_RECEIVER_USER_ID: str = ""         # 파일 받을 사용자 ID (FA 담당자)
    KNOX_MESSENGER_ENABLED: bool = False    # Knox Messenger 전송 활성화 여부
    # ─── Knox Teams (채널 파일 전송) ─────────────────────────────────────────
    # 스테이지: https://openapi.stage.samsung.net/...
    # 운  영:  https://openapi.samsung.net/...
    TEAMS_FILE_API_URL: str = ""     # Knox Teams 파일 전송 API URL (전체 경로)
    TEAMS_API_KEY: str = ""          # Knox Teams API 인증 키 (필요 시)
    TEAMS_CHANNEL_ID: str = ""       # 전송할 채널/채팅방 ID

    # ─── 개발/테스트 옵션 ────────────────────────────────────────────────────
    # MOCK_MODE=true 시 Superset 실제 조회 없이 더미 데이터로 파이프라인 테스트
    MOCK_MODE: bool = False
    # GROUPED_TABLE_DISPLAY=true 시 표를 그룹별(위치/횟수/품질) 형식으로 표시
    GROUPED_TABLE_DISPLAY: bool = False
    # AI Agent 분석 활성화 여부 (false 시 스킵)
    AI_AGENT_ENABLED: bool = False
    # 기지국 정보 조회 활성화 여부 (false 시 스킵)
    STATION_SCRAPER_ENABLED: bool = False

    # ─── Qings 사전 쿼리 (Pre-fetch) ─────────────────────────────────────────
    QINGS_URL: str = "qings.sec.samsung.net"
    QINGS_HEADLESS: bool = False          # SSO 처리 위해 기본 headful
    QINGS_USERNAME: str = "sujin06.bae"
    QINGS_PASSWORD: str = "tnwls1094!"
    QINGS_SN_COLUMN: str = "제조번호"            # SN 컬럼명 (이름으로 못 찾으면 COL_IDX 사용)
    QINGS_SN_COL_IDX: int = 6                  # G열 (0-based: A=0, B=1, ..., G=6)
    QINGS_DATE_COLUMN: str = "SEQ_NO"          # A열 — 날짜 컬럼명 (앞 8자리 YYYYMMDD)
    QINGS_DATE_LOOKBACK_DAYS: int = 7          # 오늘로부터 몇 일 전까지 포함
    QINGS_SYMPTOM_COLUMN: str = "증상명"        # (미사용 — 날짜 필터로 대체)
    QINGS_SYMPTOM_KEYWORDS: list[str] = ["통화", "수화", "송화", "데이터 접속"]
    PREFETCH_ENABLED: bool = True         # 평일 9시 자동 사전 쿼리 활성화
    CACHE_MAX_AGE_HOURS: int = 72        # 캐시 유효 시간 (시간)

    # ─── 메일 다운로더 (FA 미결건 엑셀 자동 수집) ───────────────────────────────
    MAIL_ENABLED: bool = False              # True 시 매일 17시 자동 실행
    MAIL_URL: str = "https://www.samsung.net"
    MAIL_USERNAME: str = "sujin06.bae"     # samsung.net 로그인 ID
    MAIL_PASSWORD: str = "tnwls1094!"      # samsung.net 로그인 PW
    MAIL_FOLDER_NAME: str = "FA 미결건"     # 대상 메일함 이름
    MAIL_SAVE_DIR: str = ""                 # 비워두면 CSV_DOWNLOAD_PATH/FAdata 사용
    MAIL_SCHEDULE_HOUR: int = 17            # 자동 실행 시각 (24h, 기본 17시)
    MAIL_HEADLESS: bool = False             # 메일 브라우저 headless 여부

    # ─── FastAPI 서버 ────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 80
    LOG_LEVEL: str = "INFO"
    # 외부에서 접근 가능한 서버 base URL (챗봇에 분석 결과 URL 전송 시 사용)
    BASE_URL: str = "http://10.246.9.74"

    # ─── 쿼리 조회 기간 ──────────────────────────────────────────────────────
    QUERY_LOOKBACK_DAYS: int = 14       # SQL INTERVAL N DAY (데이터 조회 기간)
    BATCH_SN_LIMIT: int = 200           # 마지막 N개만 실행 (0 = 전체)
    BATCH_CONCURRENCY: int = 3          # 동시 쿼리 실행 수

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
