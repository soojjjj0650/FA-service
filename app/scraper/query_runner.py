"""
Query Runner - Superset SQL Lab 자동화

흐름:
  1. BrowserPool에서 컨텍스트 획득
  2. Superset SQL Lab 접속 (세션 재사용)
  3. SN 기반 SQL 쿼리 자동 입력 (Ace Editor)
  4. Run 버튼 클릭 → 결과 대기 (최대 1시간)
  5. Download to CSV 클릭 → 지정 폴더에 저장
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from playwright.async_api import BrowserContext, Page, TimeoutError as PlaywrightTimeout

from app.config import settings
from app.scraper.browser_pool import browser_pool
from app.scraper.session_manager import session_manager, SessionExpiredNotice

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], Awaitable[None]]


@dataclass
class QueryResult:
    sn: str
    success: bool
    csv_path: str | None = None
    rows: list[dict[str, Any]] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    error: str | None = None
    session_expired: bool = False

    @property
    def row_count(self) -> int:
        return len(self.rows)


class QueryRunner:
    """SN을 받아 Superset SQL Lab에서 쿼리를 실행하고 CSV를 다운로드합니다."""

    SUPERSET_URL = settings.PORTAL_URL
    DOWNLOAD_DIR = settings.CSV_DOWNLOAD_PATH

    # ─── SQL 쿼리 템플릿 ─────────────────────────────────────────────────────
    SQL_TEMPLATE = """\
with Data_SN as (
    SELECT srl_num as SN, rand_id as un
    FROM bigdata-dqa-data.dqa_public_data.tw_term_agree_dvc_bas
    WHERE srl_num like '{sn}'
)
SELECT yymmddcrt as Date, SUBSTR(generation_timestamp,12,8) AS Time, feature,custom_value
FROM `bigdata-dqa-data.mobile_udc`.to_udc_modem INNER JOIN Data_SN USING (un)
WHERE p_yymmddval between DATE_SUB(current_date(), INTERVAL 14 DAY) and current_date()
ORDER by Date,Time"""

    async def run(
        self,
        sn: str,
        progress_callback: ProgressCallback | None = None,
    ) -> QueryResult:
        """
        SN에 대해 SQL 쿼리를 실행하고 CSV를 다운로드합니다.

        Args:
            sn: 단말기 시리얼 넘버
            progress_callback: 진행 상태 콜백 async fn(message: str)
        """
        logger.info(f"쿼리 시작 - SN: {sn}")

        async def notify(msg: str):
            logger.debug(f"[{sn}] {msg}")
            if progress_callback:
                await progress_callback(msg)

        try:
            async with browser_pool.acquire() as context:
                return await self._execute_query(context, sn, notify)
        except SessionExpiredNotice as e:
            msg = str(e)
            await notify("세션 만료 - 수동 재로그인 필요 (python scripts/manual_login.py)")
            logger.warning(f"세션 만료로 쿼리 중단 [{sn}]")
            return QueryResult(sn=sn, success=False, error=msg, session_expired=True)
        except Exception as e:
            logger.error(f"쿼리 실패 [{sn}]: {e}")
            return QueryResult(sn=sn, success=False, error=str(e))

    # ─────────────────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────────────────

    async def _execute_query(
        self,
        context: BrowserContext,
        sn: str,
        notify: ProgressCallback,
    ) -> QueryResult:
        page = await context.new_page()

        try:
            # 1. SQL Lab 접속
            await notify("Superset SQL Lab 접속 중...")
            await page.goto(self.SUPERSET_URL, wait_until="networkidle", timeout=30_000)

            # 세션 만료 확인 (로그인 페이지로 리디렉트)
            if "login" in page.url.lower() or "userNameInput" in await page.content():
                session_manager.mark_expired()
                raise SessionExpiredNotice(
                    "Superset 세션이 만료되었습니다.\n"
                    "재로그인: python scripts/manual_login.py"
                )

            # 2. SQL 쿼리 입력
            await notify(f"SQL 쿼리 입력 중... (SN: {sn})")
            sql = self.SQL_TEMPLATE.format(sn=sn.strip())
            await self._input_query(page, sql)

            # 3. Run 버튼 클릭 + 완료 대기
            await notify(
                f"쿼리 실행 중... (SN: {sn}) - 최대 {settings.QUERY_TIMEOUT_SECONDS // 60}분 소요"
            )
            await self._run_and_wait(page)

            # 4. CSV 다운로드
            await notify("CSV 다운로드 중...")
            csv_path = await self._download_csv(context, page, sn)

            await notify(f"완료 - 저장: {csv_path}")
            return QueryResult(sn=sn, success=True, csv_path=csv_path)

        finally:
            await page.close()

    async def _input_query(self, page: Page, sql: str) -> None:
        """Ace Editor에 SQL을 입력합니다. JS API → 마우스+키보드 → textarea 순으로 시도."""

        # 방법 1: Ace Editor JavaScript API
        try:
            await page.wait_for_selector("#ace-editor", timeout=10_000)
            escaped = sql.replace("\\", "\\\\").replace("`", "\\`")
            await page.evaluate(f"""
                var editor = ace.edit('ace-editor');
                editor.setValue(`{escaped}`, 1);
                editor.clearSelection();
            """)
            logger.debug("Ace Editor: JS API로 쿼리 입력 완료")
            return
        except Exception as e:
            logger.debug(f"Ace Editor JS API 실패, 폴백 시도: {e}")

        # 방법 2: 마우스 클릭 후 Ctrl+A → 타이핑
        try:
            editor_el = await page.query_selector(".ace_editor")
            if editor_el:
                bbox = await editor_el.bounding_box()
                await page.mouse.click(bbox["x"] + bbox["width"] / 2, bbox["y"] + bbox["height"] / 2)
                await page.keyboard.press("Control+a")
                await page.keyboard.type(sql)
                logger.debug("Ace Editor: 마우스+키보드로 쿼리 입력 완료")
                return
        except Exception as e:
            logger.debug(f"Ace Editor 마우스 입력 실패: {e}")

        # 방법 3: textarea 직접 조작
        for sel in [".ace_text-input", "textarea.ace_text-input", ".ace_editor textarea"]:
            try:
                await page.wait_for_selector(sel, timeout=5_000)
                await page.click(sel)
                await page.keyboard.press("Control+a")
                await page.keyboard.type(sql)
                logger.debug(f"Ace Editor: textarea({sel})로 쿼리 입력 완료")
                return
            except Exception:
                continue

        raise RuntimeError("SQL 입력 실패: Ace Editor를 찾을 수 없습니다.")

    async def _run_and_wait(self, page: Page) -> None:
        """Run 버튼 클릭 후 쿼리 완료까지 대기합니다 (최대 1시간)."""
        timeout_ms = settings.QUERY_TIMEOUT_SECONDS * 1000

        # Run 버튼 클릭
        await page.wait_for_selector('button:has-text("Run")', timeout=10_000)
        await page.click('button:has-text("Run")')

        # 실행 시작 대기 (스피너 등장)
        try:
            await page.wait_for_selector(
                '.ant-spin, .loading, [class*="loading"]',
                state="visible",
                timeout=15_000,
            )
        except PlaywrightTimeout:
            pass  # 일부 환경에서 즉시 완료될 수 있음

        # 완료 대기: "Download to CSV" 버튼 등장
        await page.wait_for_selector(
            'button:has-text("Download to CSV")',
            state="visible",
            timeout=timeout_ms,
        )

        # 에러 메시지 확인
        error_el = await page.query_selector('[class*="QueryTable--error"], [class*="error-message"]')
        if error_el:
            error_text = await error_el.inner_text()
            raise RuntimeError(f"쿼리 실행 오류: {error_text.strip()}")

    async def _download_csv(self, context: BrowserContext, page: Page, sn: str) -> str:
        """Download to CSV 버튼 클릭 후 파일을 지정 경로에 저장합니다."""
        os.makedirs(self.DOWNLOAD_DIR, exist_ok=True)
        save_path = os.path.join(self.DOWNLOAD_DIR, f"{sn}_inputdata.csv")

        async with page.expect_download(timeout=60_000) as dl_info:
            await page.click('button:has-text("Download to CSV")')
        download = await dl_info.value
        await download.save_as(save_path)

        logger.info(f"CSV 저장 완료: {save_path}")
        return save_path


# 싱글턴 인스턴스
query_runner = QueryRunner()
