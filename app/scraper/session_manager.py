"""
Session Manager - 로그인 세션을 한 번만 수행하고 재사용

핵심 전략:
  1. 최초 실행 시 실제 브라우저로 로그인 → storage_state(쿠키+localStorage) 파일 저장
  2. 이후 모든 브라우저 컨텍스트는 저장된 storage_state 로드 → 로그인 불필요
  3. 세션 만료(401/redirect) 감지 시 자동 재로그인 후 storage_state 갱신
"""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from app.config import settings

logger = logging.getLogger(__name__)


class SessionManager:
    """포털 로그인 세션을 관리합니다."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._session_file: Path = settings.SESSION_FILE
        self._session_file.parent.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._browser: Browser | None = None
        self._logged_in = False

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    async def ensure_session(self) -> None:
        """세션이 유효한지 확인하고, 없으면 로그인을 수행합니다."""
        async with self._lock:
            if self._session_file.exists() and self._logged_in:
                logger.debug("세션 파일 존재 - 재사용")
                return
            await self._login()

    async def get_storage_state(self) -> str:
        """저장된 storage_state 파일 경로를 반환합니다."""
        await self.ensure_session()
        return str(self._session_file)

    async def invalidate_session(self) -> None:
        """세션을 무효화하고 재로그인을 강제합니다."""
        async with self._lock:
            self._logged_in = False
            if self._session_file.exists():
                self._session_file.unlink()
            logger.info("세션 무효화됨 - 다음 요청 시 재로그인")

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    # ─────────────────────────────────────────────────────────────────────────
    # Private
    # ─────────────────────────────────────────────────────────────────────────

    async def _login(self) -> None:
        """포털에 로그인하고 storage_state를 파일로 저장합니다."""
        logger.info("포털 로그인 시작...")

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        # 로그인 전용 브라우저 (일회성)
        browser = await self._playwright.chromium.launch(
            headless=settings.BROWSER_HEADLESS
        )
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(settings.PORTAL_LOGIN_URL, wait_until="networkidle")
            await self._fill_login_form(page)
            await self._verify_login(page)

            # 세션 저장
            await context.storage_state(path=str(self._session_file))
            self._logged_in = True

            logger.info(
                f"로그인 성공 - 세션 저장: {self._session_file} "
                f"({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
            )
        except Exception as e:
            logger.error(f"로그인 실패: {e}")
            raise
        finally:
            await context.close()
            await browser.close()

    async def _fill_login_form(self, page: Page) -> None:
        """로그인 폼을 채우고 제출합니다. 실제 포털 HTML에 맞게 수정하세요."""
        # ──── 실제 포털의 input selector로 교체 필요 ────────────────────────
        await page.fill('input[name="username"]', settings.PORTAL_USERNAME)
        await page.fill('input[name="password"]', settings.PORTAL_PASSWORD)
        await page.click('button[type="submit"]')
        # 로그인 완료 대기 (포털 메인 페이지 로드)
        await page.wait_for_url(
            f"{settings.PORTAL_URL}/**",
            timeout=30_000,
        )

    async def _verify_login(self, page: Page) -> None:
        """로그인 성공 여부를 확인합니다."""
        url = page.url
        if "login" in url.lower() or "error" in url.lower():
            raise RuntimeError(
                f"로그인 후에도 로그인 페이지에 머물러 있습니다: {url}\n"
                "USERNAME/PASSWORD를 확인하세요."
            )
        logger.debug(f"로그인 확인 완료 - 현재 URL: {url}")


# 싱글턴 인스턴스
session_manager = SessionManager()
