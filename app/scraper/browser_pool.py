"""
Browser Pool - 최대 N개의 브라우저를 동시에 관리

핵심 설계:
  - asyncio.Semaphore로 동시 실행 수를 MAX_CONCURRENT_BROWSERS(기본 5)로 제한
  - 각 브라우저 컨텍스트는 동일한 storage_state(로그인 세션)를 재사용
  - 컨텍스트별로 독립된 쿠키/탭 공간 → 서로 간섭 없음
  - 세션 만료 감지 시 SessionManager에 재로그인 요청
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright

from app.config import settings
from app.scraper.session_manager import session_manager

logger = logging.getLogger(__name__)


class BrowserPool:
    """
    최대 MAX_CONCURRENT_BROWSERS개의 Playwright 브라우저 컨텍스트를
    비동기적으로 관리하는 풀입니다.
    """

    def __init__(self, max_size: int = settings.MAX_CONCURRENT_BROWSERS):
        self._max_size = max_size
        self._semaphore = asyncio.Semaphore(max_size)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._init_lock = asyncio.Lock()
        self._active_count = 0

    # ─────────────────────────────────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────────────────────────────────

    async def startup(self) -> None:
        """서버 시작 시 브라우저 프로세스를 초기화합니다."""
        async with self._init_lock:
            if self._playwright is None:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=settings.BROWSER_HEADLESS,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                )
                logger.info(
                    f"브라우저 풀 초기화 완료 "
                    f"(최대 동시 실행: {self._max_size}개)"
                )

    async def shutdown(self) -> None:
        """서버 종료 시 모든 브라우저를 정리합니다."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        await session_manager.close()
        logger.info("브라우저 풀 종료")

    # ─────────────────────────────────────────────────────────────────────────
    # Context manager
    # ─────────────────────────────────────────────────────────────────────────

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[BrowserContext]:
        """
        브라우저 컨텍스트를 빌려줍니다.

        사용 예시:
            async with browser_pool.acquire() as context:
                page = await context.new_page()
                ...
        """
        # 동시 실행 수 제한 (5개 초과 시 대기)
        await self._semaphore.acquire()
        self._active_count += 1
        logger.debug(
            f"브라우저 컨텍스트 획득 "
            f"(활성: {self._active_count}/{self._max_size})"
        )

        context = await self._create_context()
        try:
            yield context
        except Exception as e:
            # 세션 만료 감지
            if self._is_session_expired(e):
                logger.warning("세션 만료 감지 - 재로그인 시도")
                await session_manager.invalidate_session()
            raise
        finally:
            await context.close()
            self._active_count -= 1
            self._semaphore.release()
            logger.debug(
                f"브라우저 컨텍스트 반환 "
                f"(활성: {self._active_count}/{self._max_size})"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────────────────

    async def _create_context(self) -> BrowserContext:
        """저장된 세션(storage_state)을 로드한 새 브라우저 컨텍스트를 생성합니다."""
        if self._browser is None:
            await self.startup()

        # 세션 파일 확보 (없으면 로그인 수행)
        storage_state_path = await session_manager.get_storage_state()

        context = await self._browser.new_context(
            storage_state=storage_state_path,
            viewport={"width": 1920, "height": 1080},
            # 봇 감지 우회
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
        )
        return context

    @staticmethod
    def _is_session_expired(error: Exception) -> bool:
        msg = str(error).lower()
        return any(kw in msg for kw in ["login", "unauthorized", "401", "session"])

    @property
    def active_count(self) -> int:
        return self._active_count

    @property
    def max_size(self) -> int:
        return self._max_size


# 싱글턴 풀 인스턴스
browser_pool = BrowserPool()
