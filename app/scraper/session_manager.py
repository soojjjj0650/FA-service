"""
Session Manager - 로그인 세션 관리

지문인증(MFA) 대응 전략:
  - 자동 로그인 불가 → 수동 로그인 스크립트(scripts/manual_login.py)로 최초 1회 세션 저장
  - 이후 모든 브라우저 컨텍스트가 storage_state(쿠키+localStorage) 재사용
  - 세션 만료 감지 시 → SessionExpiredNotice 발생 → 챗봇 UI에 알림 표시

세션 만료 감지:
  - 브라우저가 포털 접속 시 로그인 페이지로 리디렉트 → 만료 판정
  - 관리자가 scripts/manual_login.py 재실행으로 복구
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

SESSION_META_FILE = settings.SESSION_FILE.parent / "session_meta.json"


class SessionExpiredNotice(Exception):
    """
    세션이 만료되어 수동 재로그인이 필요함을 알리는 예외.
    MFA(지문인증)가 있으므로 자동 재로그인 불가.
    """
    pass


class SessionManager:
    """포털 로그인 세션을 관리합니다."""

    def __init__(self):
        self._session_file: Path = settings.SESSION_FILE
        self._session_file.parent.mkdir(parents=True, exist_ok=True)
        self._expired = False  # 만료 상태 캐시

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def get_storage_state_path(self) -> str:
        """
        저장된 storage_state 파일 경로를 반환합니다.
        세션 파일이 없으면 수동 로그인을 안내하는 예외를 발생시킵니다.
        """
        if self._expired:
            raise SessionExpiredNotice(self._expired_message())

        if not self._session_file.exists():
            raise SessionExpiredNotice(
                "세션 파일이 없습니다. 먼저 수동 로그인을 완료해 주세요.\n"
                "  → 터미널에서: python scripts/manual_login.py"
            )

        return str(self._session_file)

    def mark_expired(self) -> None:
        """세션 만료를 표시합니다 (자동 재로그인 없음 - MFA 때문)."""
        self._expired = True
        logger.warning("세션 만료 감지 - 수동 재로그인 필요 (python scripts/manual_login.py)")

    def mark_refreshed(self) -> None:
        """수동 로그인 완료 후 만료 상태를 해제합니다 (/api/session/reset 호출 시)."""
        self._expired = False
        logger.info("세션 복구 완료")

    def invalidate(self) -> None:
        """세션 파일을 삭제하고 만료 상태로 전환합니다."""
        if self._session_file.exists():
            self._session_file.unlink()
        if SESSION_META_FILE.exists():
            SESSION_META_FILE.unlink()
        self._expired = True
        logger.info("세션 무효화 완료")

    def is_expired(self) -> bool:
        return self._expired or not self._session_file.exists()

    def session_info(self) -> dict:
        """세션 상태 정보를 반환합니다 (API status용)."""
        if not self._session_file.exists():
            return {
                "status": "no_session",
                "saved_at": None,
                "message": "세션 없음 - python scripts/manual_login.py 실행 필요",
            }

        meta = {}
        if SESSION_META_FILE.exists():
            try:
                meta = json.loads(SESSION_META_FILE.read_text())
            except Exception:
                pass

        return {
            "status": "expired" if self._expired else "active",
            "saved_at": meta.get("saved_at"),
            "portal_url": meta.get("portal_url"),
            "message": (
                "세션 만료 - python scripts/manual_login.py 실행 필요"
                if self._expired
                else "세션 정상"
            ),
        }

    async def close(self) -> None:
        pass  # 별도 cleanup 불필요

    # ─────────────────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _expired_message() -> str:
        return (
            "포털 세션이 만료되었습니다.\n\n"
            "지문인증이 필요하므로 아래 명령어로 수동 재로그인 후 서비스를 재개해 주세요:\n"
            "  python scripts/manual_login.py\n\n"
            "재로그인 후 챗봇 화면을 새로고침하면 자동으로 복구됩니다."
        )


# 싱글턴 인스턴스
session_manager = SessionManager()
