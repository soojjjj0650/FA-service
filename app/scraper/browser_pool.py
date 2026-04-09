"""
Browser Pool - 최대 N개의 브라우저를 동시에 관리

핵심 설계:
  - asyncio.Semaphore로 동시 실행 수를 MAX_CONCURRENT_BROWSERS(기본 5)로 제한
  - 각 브라우저 컨텍스트는 동일한 storage_state(로그인 세션)를 재사용
  - 컨텍스트별로 독립된 쿠키/탭 공간 → 서로 간섭 없음
  - 세션 만료 감지 시 SessionManager에 재로그인 요청
  - Edge 브라우저 지원 (Windows: EDGE_EXECUTABLE_PATH)
  - CSV 다운로드를 위한 accept_downloads=True 컨텍스트 지원
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright

from app.config import settings
from app.scraper.session_manager import session_manager, SessionExpiredNotice

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

                launch_kwargs = dict(
                    headless=settings.BROWSER_HEADLESS,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                )
                # Edge 브라우저 경로가 존재하면 사용 (Windows)
                edge_path = settings.EDGE_EXECUTABLE_PATH
                if edge_path and os.path.exists(edge_path):
                    launch_kwargs["executable_path"] = edge_path
                    logger.info(f"Edge 브라우저 사용: {edge_path}")

                self._browser = await self._playwright.chromium.launch(**launch_kwargs)
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
            # 세션 만료 감지 (MFA로 인해 자동 재로그인 불가 → mark_expired만 표시)
            if self._is_session_expired(e):
                logger.warning("세션 만료 감지 - 수동 재로그인 필요 (MFA)")
                session_manager.mark_expired()
            raise
        finally:
            try:
                await asyncio.wait_for(context.close(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("브라우저 컨텍스트 닫기 타임아웃 → Playwright 완전 재시작")
                try:
                    if self._playwright:
                        await asyncio.wait_for(self._playwright.stop(), timeout=2.0)
                except Exception:
                    pass
                self._browser = None
                self._playwright = None
                await self.startup()
            except Exception as e:
                logger.debug(f"브라우저 컨텍스트 닫기 오류 (무시): {e}")
            self._active_count -= 1
            self._semaphore.release()
            logger.debug(
                f"브라우저 컨텍스트 반환 "
                f"(활성: {self._active_count}/{self._max_size})"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────────────────

    async def _create_context(self, accept_downloads: bool = True) -> BrowserContext:
        """저장된 세션(storage_state)을 로드한 새 브라우저 컨텍스트를 생성합니다."""
        if self._browser is None:
            await self.startup()

        # 세션 파일 확보 (없으면 SessionExpiredNotice 발생)
        storage_state_path = session_manager.get_storage_state_path()

        try:
            context = await self._browser.new_context(
                storage_state=storage_state_path,
                viewport={"width": 1920, "height": 1080},
                accept_downloads=accept_downloads,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
                ),
            )
            return context
        except Exception as e:
            err = str(e).lower()
            if "connection closed" in err or "target closed" in err or "browser has been closed" in err:
                logger.warning("브라우저 연결 끊김 감지 - 재시작 중...")
                self._browser = None
                self._playwright = None
                await self.startup()
                return await self._browser.new_context(
                    storage_state=storage_state_path,
                    viewport={"width": 1920, "height": 1080},
                    accept_downloads=accept_downloads,
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
                    ),
                )
            raise

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
