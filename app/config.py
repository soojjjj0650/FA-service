"""
FA Chatbot Service - Configuration
"""
from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    # ─── 내부 SQL 포털 (웹 스크래핑 대상) ───────────────────────────────────
    PORTAL_URL: str = "https://internal-portal.company.com"
    PORTAL_LOGIN_URL: str = "https://internal-portal.company.com/login"
    PORTAL_QUERY_URL: str = "https://internal-portal.company.com/sql-query"

    PORTAL_USERNAME: str = ""
    PORTAL_PASSWORD: str = ""

    # ─── 세션 저장 경로 ──────────────────────────────────────────────────────
    SESSION_FILE: Path = BASE_DIR / "data" / "sessions" / "portal_session.json"

    # ─── 브라우저 풀 설정 ────────────────────────────────────────────────────
    MAX_CONCURRENT_BROWSERS: int = 5          # 동시 실행 브라우저 최대 수
    BROWSER_HEADLESS: bool = True             # CI/서버 환경에서는 True
    QUERY_TIMEOUT_SECONDS: int = 1200        # 쿼리 타임아웃 (20분, 여유 있게)
    SESSION_REUSE: bool = True               # 세션 재사용 여부

    # ─── Anthropic Claude API ────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-opus-4-6"
    ANTHROPIC_MAX_TOKENS: int = 4096

    # ─── FastAPI 서버 ────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
