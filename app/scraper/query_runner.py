"""
Query Runner - SN을 받아 웹 스크래핑으로 SQL 쿼리를 실행하고 결과를 반환

흐름:
  1. BrowserPool에서 컨텍스트 획득
  2. 포털 SQL 쿼리 페이지로 이동
  3. SN 기반 SQL 쿼리 입력 & 실행
  4. 결과 테이블 파싱 (5~15분 소요 → 비동기 대기)
  5. 구조화된 데이터 반환
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import BrowserContext, Page, TimeoutError as PlaywrightTimeout

from app.config import settings
from app.scraper.browser_pool import browser_pool
from app.scraper.session_manager import session_manager

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    sn: str
    success: bool
    rows: list[dict[str, Any]] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    error: str | None = None
    raw_html: str | None = None

    @property
    def row_count(self) -> int:
        return len(self.rows)


class QueryRunner:
    """SN을 입력으로 받아 웹 포털에서 SQL 쿼리를 실행합니다."""

    # ─── SN 기반 SQL 쿼리 템플릿 (실제 쿼리로 교체 필요) ─────────────────────
    SQL_TEMPLATE = """
        SELECT
            d.serial_number,
            d.device_model,
            d.manufacture_date,
            d.firmware_version,
            d.status,
            c.customer_name,
            c.contract_start,
            c.contract_end,
            s.last_service_date,
            s.service_type,
            s.engineer_name,
            s.service_note
        FROM devices d
        LEFT JOIN customers c ON d.customer_id = c.id
        LEFT JOIN service_history s ON d.id = s.device_id
        WHERE d.serial_number = '{sn}'
        ORDER BY s.last_service_date DESC
    """

    async def run(
        self,
        sn: str,
        progress_callback=None,
    ) -> QueryResult:
        """
        주어진 SN에 대해 SQL 쿼리를 실행하고 결과를 반환합니다.

        Args:
            sn: 단말기 시리얼 넘버
            progress_callback: 진행 상태 콜백 async fn(message: str)
        """
        logger.info(f"쿼리 시작 - SN: {sn}")

        async def notify(msg: str):
            logger.debug(f"[{sn}] {msg}")
            if progress_callback:
                await progress_callback(msg)

        retry_count = 0
        max_retries = 2

        while retry_count <= max_retries:
            try:
                async with browser_pool.acquire() as context:
                    result = await self._execute_query(context, sn, notify)
                    return result
            except SessionExpiredError:
                await notify("세션 만료 - 재로그인 중...")
                await session_manager.invalidate_session()
                retry_count += 1
            except Exception as e:
                logger.error(f"쿼리 실패 [{sn}]: {e}")
                return QueryResult(sn=sn, success=False, error=str(e))

        return QueryResult(sn=sn, success=False, error="재시도 초과 - 세션 복구 실패")

    # ─────────────────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────────────────

    async def _execute_query(
        self,
        context: BrowserContext,
        sn: str,
        notify,
    ) -> QueryResult:
        page = await context.new_page()

        try:
            await notify("포털 접속 중...")
            await page.goto(
                settings.PORTAL_QUERY_URL,
                wait_until="networkidle",
                timeout=30_000,
            )

            # 세션 만료 확인 (로그인 페이지로 리디렉트되는 경우)
            if "login" in page.url.lower():
                raise SessionExpiredError("세션 만료 - 로그인 페이지로 리디렉트됨")

            await notify("SQL 쿼리 입력 중...")
            sql = self.SQL_TEMPLATE.format(sn=sn.strip())
            await self._input_query(page, sql)

            await notify(f"쿼리 실행 중... (SN: {sn}) - 최대 {settings.QUERY_TIMEOUT_SECONDS // 60}분 소요")
            await self._submit_and_wait(page)

            await notify("결과 파싱 중...")
            result = await self._parse_result(page, sn)

            await notify(f"완료 - {result.row_count}건 조회")
            return result

        finally:
            await page.close()

    async def _input_query(self, page: Page, sql: str) -> None:
        """
        SQL 입력 영역에 쿼리를 입력합니다.
        ─── 실제 포털 HTML selector로 교체 필요 ────────────────────────────────
        """
        # CodeMirror / textarea / Monaco Editor 등 포털 에디터 유형에 따라 선택
        editor_selector = 'textarea#sql-editor, .CodeMirror textarea, #query-input'

        await page.wait_for_selector(editor_selector, timeout=15_000)

        # 기존 내용 지우기
        await page.click(editor_selector)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Delete")

        # SQL 입력
        await page.fill(editor_selector, sql)

    async def _submit_and_wait(self, page: Page) -> None:
        """
        쿼리를 실행하고 결과가 나올 때까지 대기합니다.
        ─── 실제 포털 버튼/결과 selector로 교체 필요 ──────────────────────────
        """
        # 실행 버튼 클릭
        await page.click('button#run-query, button[data-action="execute"], #btn-execute')

        # 로딩 스피너가 사라질 때까지 대기 (쿼리 실행 완료)
        try:
            # 로딩 시작 대기
            await page.wait_for_selector(
                '.loading-spinner, #query-loading, [data-state="loading"]',
                state="visible",
                timeout=10_000,
            )
        except PlaywrightTimeout:
            pass  # 로딩 인디케이터가 없는 포털도 있음

        # 결과 나올 때까지 대기 (최대 QUERY_TIMEOUT_SECONDS)
        await page.wait_for_selector(
            '.result-table, #query-results table, .data-grid',
            state="visible",
            timeout=settings.QUERY_TIMEOUT_SECONDS * 1000,
        )

        # 추가 렌더링 대기
        await page.wait_for_load_state("networkidle", timeout=30_000)

    async def _parse_result(self, page: Page, sn: str) -> QueryResult:
        """
        결과 테이블을 파싱하여 구조화된 데이터로 변환합니다.
        ─── 실제 포털 결과 테이블 구조에 맞게 수정 필요 ───────────────────────
        """
        raw_html = await page.inner_html(
            '.result-table, #query-results, .data-grid',
        )

        # 컬럼 헤더 추출
        columns = await page.eval_on_selector_all(
            '.result-table thead th, #query-results th',
            'els => els.map(el => el.innerText.trim())',
        )

        # 행 데이터 추출
        rows_data = await page.eval_on_selector_all(
            '.result-table tbody tr, #query-results tbody tr',
            '''rows => rows.map(row =>
                Array.from(row.querySelectorAll("td"))
                    .map(td => td.innerText.trim())
            )''',
        )

        rows = []
        for row_values in rows_data:
            if columns and len(row_values) == len(columns):
                rows.append(dict(zip(columns, row_values)))
            else:
                rows.append({f"col_{i}": v for i, v in enumerate(row_values)})

        return QueryResult(
            sn=sn,
            success=True,
            rows=rows,
            columns=columns,
            raw_html=raw_html,
        )


class SessionExpiredError(Exception):
    pass


# 싱글턴 인스턴스
query_runner = QueryRunner()
