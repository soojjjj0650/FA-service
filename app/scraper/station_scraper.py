"""
Station Scraper - 기지국 정보 조회 (10.246.56.50:8000)

흐름:
  1. 기존 BrowserPool 컨텍스트 재사용 (별도 브라우저 실행 없음)
  2. 사업자 선택 (SKT / KT / LGU+)
  3. TAC / PCI 입력
  4. 검색 버튼 클릭
  5. 결과 테이블 전체 행 추출
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

STATION_URL = "http://10.246.56.50:8000"

# 사업자 버튼 클래스명 매핑
OPERATOR_MAP = {
    "skt":  "skt",
    "kt":   "kt",
    "lgu":  "lgu",
    "lgu+": "lgu",
    "lg":   "lgu",
}


@dataclass
class StationResult:
    operator: str
    tac: str
    pci: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    success: bool = True
    error: str | None = None

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def to_text(self) -> str:
        """챗봇/AI 입력용 텍스트 변환"""
        if not self.success:
            return f"기지국 조회 실패: {self.error}"
        if not self.rows:
            return f"[{self.operator.upper()} TAC:{self.tac} PCI:{self.pci}] 조회 결과 없음"

        lines = [f"{self.operator.upper()} / TAC:{self.tac} / PCI:{self.pci} ({self.row_count}건)"]
        for r in self.rows:
            lines.append("  " + " | ".join(f"{k}:{v}" for k, v in r.items()))
        return "\n".join(lines)


class StationScraper:
    """TAC / PCI로 기지국 정보를 조회합니다. BrowserPool을 재사용합니다."""

    URL = STATION_URL

    async def search(
        self,
        operator: str,
        tac: str,
        pci: str,
    ) -> StationResult:
        """
        Args:
            operator: 사업자 ("skt" / "kt" / "lgu")
            tac: TAC 값
            pci: PCI 값
        """
        # import here to avoid circular import
        from app.scraper.browser_pool import browser_pool

        op = OPERATOR_MAP.get(operator.lower().strip(), operator.lower().strip())
        logger.info(f"기지국 조회 시작 - operator:{op} TAC:{tac} PCI:{pci}")

        try:
            async with browser_pool.acquire() as context:
                page = await context.new_page()
                try:
                    rows = await self._scrape(page, op, tac, pci)
                    return StationResult(operator=op, tac=tac, pci=pci, rows=rows)
                finally:
                    try:
                        await page.close()
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"기지국 조회 실패: {e}")
            return StationResult(operator=op, tac=tac, pci=pci, success=False, error=str(e))

    async def _scrape(self, page: Page, operator: str, tac: str, pci: str) -> list[dict]:
        # 1. 페이지 접속
        await page.goto(self.URL, wait_until="domcontentloaded", timeout=30_000)
        try:
            await page.wait_for_load_state("networkidle", timeout=10_000)
        except PlaywrightTimeout:
            pass

        # 2. 사업자 버튼 클릭
        await page.click(f'button.operator-tab.{operator}')
        await page.wait_for_timeout(500)

        # 3. TAC 입력 (id="seach-tac" - 원본 오타 그대로)
        await page.fill('#seach-tac', tac)

        # 4. PCI 입력
        await page.fill('#search-pci', pci)

        # 5. 검색 버튼 클릭
        await page.click('button:has-text("검색")')

        # 6. 결과 테이블 대기
        try:
            await page.wait_for_selector('#station-table tr', state="visible", timeout=15_000)
        except PlaywrightTimeout:
            logger.warning("결과 테이블 감지 안됨 - 결과 없음으로 처리")
            return []

        # 7. 결과 추출: onclick 속성의 showDetail({...}) JSON 파싱
        rows: list[dict] = await page.evaluate("""
            () => {
                const trs = document.querySelectorAll('#station-table tr');
                const results = [];
                trs.forEach(tr => {
                    const onclick = tr.getAttribute('onclick') || '';
                    const match = onclick.match(/showDetail\\((.+?)\\)$/);
                    if (match) {
                        try {
                            results.push(JSON.parse(match[1]));
                        } catch(e) {
                            const tds = Array.from(tr.querySelectorAll('td'));
                            if (tds.length > 0) {
                                results.push({ raw: tds.map(td => td.innerText.trim()).join(' | ') });
                            }
                        }
                    }
                });
                return results;
            }
        """)

        logger.info(f"기지국 조회 완료: {len(rows)}건")
        return rows


# 싱글턴 인스턴스
station_scraper = StationScraper()
