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
    CSV_DOWNLOAD_PATH: str = r"C:\Users\sujin06.bae\Desktop\FA_Service_data"

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
    AI_AGENT_PROMPT_KEY: str = "prompt-rFpiB"      # 시스템 프롬프트 컴포넌트 key
    AI_AGENT_TIMEOUT: int = 120

    # ─── 회사 챗봇 웹훅 (FA 분석 완료 시 결과 push) ──────────────────────────
    CHATBOT_WEBHOOK_URL: str = "https://botbuilder.samsung.net/webhook/fa.service"

    # ─── FastAPI 서버 ────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 80
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
