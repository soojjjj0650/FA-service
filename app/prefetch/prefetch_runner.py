"""
사전 쿼리 실행기 — Qings 엑셀에서 SN 추출 후 Superset 쿼리를 사전 실행합니다.
"""
import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

from app.config import settings
from app.prefetch.cache_manager import is_cached

logger = logging.getLogger(__name__)

# ── 실행 상태 ─────────────────────────────────────────────────────────────────
_status: dict = {
    "running": False,
    "last_run": None,
    "last_result": None,
    "error": None,
}


def get_status() -> dict:
    return dict(_status)


# ── CSV → Excel 변환 ──────────────────────────────────────────────────────────
def _csv_to_xlsx(csv_path: str) -> str | None:
    """CSV 파일을 같은 경로에 xlsx로 저장합니다."""
    import csv as csv_mod
    import openpyxl
    from pathlib import Path

    p = Path(csv_path)
    xlsx_path = p.with_suffix(".xlsx")
    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        with open(p, encoding="utf-8-sig", newline="") as f:
            for row in csv_mod.reader(f):
                ws.append(row)
        wb.save(xlsx_path)
        logger.info(f"[Prefetch] Excel 저장 완료 → {xlsx_path}")
        return str(xlsx_path)
    except Exception as e:
        logger.warning(f"[Prefetch] Excel 변환 실패({csv_path}): {e}")
        return None


# ── SN 추출 ───────────────────────────────────────────────────────────────────
def _iter_excel_rows(excel_path: str):
    """xls/xlsx 모두 지원하는 행 이터레이터. (headers, row_iter) 반환."""
    ext = str(excel_path).lower()

    if ext.endswith(".xls"):
        # 1) xlrd (진짜 BIFF 포맷)
        try:
            import xlrd
            wb = xlrd.open_workbook(excel_path)
            ws = wb.sheet_by_index(0)
            headers = [str(ws.cell_value(0, c)).strip() for c in range(ws.ncols)]
            def _xlrd_rows():
                for r in range(1, ws.nrows):
                    yield tuple(ws.cell_value(r, c) for c in range(ws.ncols))
            return headers, _xlrd_rows()
        except Exception as e:
            logger.warning(f"[Prefetch] xlrd 실패({e}), openpyxl 시도...")

        # 2) openpyxl (xlsx 확장자를 .xls로 저장한 경우)
        try:
            import openpyxl
            wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
            ws = wb.active
            rows = ws.iter_rows(values_only=True)
            header_row = next(rows)
            headers = [str(v).strip() if v is not None else "" for v in header_row]
            return headers, rows
        except Exception as e:
            logger.warning(f"[Prefetch] openpyxl 실패({e}), HTML 파싱 시도...")

        # 3) HTML 테이블 (한국 기업 시스템에서 흔한 HTML-as-XLS)
        import html.parser, pathlib

        class _TableParser(html.parser.HTMLParser):
            def __init__(self):
                super().__init__()
                self.rows: list[list[str]] = []
                self._row: list[str] = []
                self._cell = False
                self._data: list[str] = []
            def handle_starttag(self, tag, attrs):
                if tag in ("tr",):
                    self._row = []
                elif tag in ("td", "th"):
                    self._cell = True
                    self._data = []
            def handle_endtag(self, tag):
                if tag in ("td", "th"):
                    self._row.append("".join(self._data).strip())
                    self._cell = False
                elif tag == "tr" and self._row:
                    self.rows.append(self._row)
            def handle_data(self, data):
                if self._cell:
                    self._data.append(data)

        raw = pathlib.Path(excel_path).read_bytes()
        for enc in ("utf-8", "euc-kr", "cp949"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = raw.decode("utf-8", errors="replace")

        parser = _TableParser()
        parser.feed(text)
        if not parser.rows:
            raise ValueError("HTML 파싱 결과 없음")

        # 첫 행이 제목일 수 있으므로 sn_column이 있는 행을 헤더로 사용
        sn_col = settings.QINGS_SN_COLUMN
        header_idx = 0
        for i, row in enumerate(parser.rows):
            if sn_col in [c.strip() for c in row]:
                header_idx = i
                logger.info(f"[Prefetch] HTML 헤더 행: {i}번째 행")
                break
        else:
            logger.warning(f"[Prefetch] '{sn_col}' 헤더 못 찾음 — 첫 행 사용. 실제 헤더: {parser.rows[0][:5]}")

        headers = [c.strip() for c in parser.rows[header_idx]]
        data_rows = parser.rows[header_idx + 1:]
        def _html_rows():
            for r in data_rows:
                yield tuple(r)
        return headers, _html_rows()

    else:
        import openpyxl
        wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        header_row = next(rows)
        headers = [str(v).strip() if v is not None else "" for v in header_row]
        return headers, rows


def extract_sns_from_excel(excel_path: str, sn_column: str | None = None) -> list[str]:
    """xlsx/xls에서 SN 목록을 추출합니다.

    날짜 필터: SEQ_NO 앞 8자리(YYYYMMDD) 기준 오늘로부터 QINGS_DATE_LOOKBACK_DAYS 이내 행만 포함.
    SN 추출: SER_NO(E열), 중복 제거.
    """
    from datetime import date, timedelta

    if sn_column is None:
        sn_column = settings.QINGS_SN_COLUMN

    date_col     = settings.QINGS_DATE_COLUMN
    lookback     = settings.QINGS_DATE_LOOKBACK_DAYS
    cutoff       = (date.today() - timedelta(days=lookback)).strftime("%Y%m%d")

    headers, row_iter = _iter_excel_rows(excel_path)

    if sn_column not in headers:
        logger.warning(f"[Prefetch] SN 열 '{sn_column}' 없음. 헤더: {headers[:10]}")
        return []

    sn_idx   = headers.index(sn_column)
    date_idx = headers.index(date_col) if date_col in headers else None

    if date_idx is None:
        logger.warning(f"[Prefetch] 날짜 열 '{date_col}' 없음 — 날짜 필터 없이 전체 SN 추출")

    seen: set[str] = set()
    sns:  list[str] = []
    skipped = 0

    for row in row_iter:
        # 날짜 필터: SEQ_NO 앞 8자리 >= cutoff
        if date_idx is not None:
            raw_date = str(row[date_idx]).strip() if date_idx < len(row) and row[date_idx] else ""
            row_date = raw_date[:8]
            if len(row_date) < 8 or row_date < cutoff:
                skipped += 1
                continue

        val = row[sn_idx] if sn_idx < len(row) else None
        if val:
            sn = str(val).strip().upper()
            if sn and sn not in seen:
                seen.add(sn)
                sns.append(sn)

    logger.info(f"[Prefetch] SN {len(sns)}개 추출 (기준일 {cutoff} 이후 / {skipped}개 제외)")
    return sns


# ── SN 목록으로 사전 쿼리 ────────────────────────────────────────────────────
async def run_prefetch_for_sns(sns: list[str]) -> dict:
    """주어진 SN 목록에 대해 캐시 없는 항목만 Superset 쿼리를 실행합니다."""
    from app.scraper.query_runner import query_runner

    if _status["running"]:
        logger.warning("[Prefetch] 이미 실행 중입니다.")
        return {"status": "already_running"}

    _status["running"] = True
    _status["error"] = None

    uncached = [sn for sn in sns if not is_cached(sn)]
    cached_count = len(sns) - len(uncached)
    result = {
        "total": len(sns),
        "cached": cached_count,
        "queried": 0,
        "failed": 0,
        "failed_sns": [],
    }

    logger.info(
        f"[Prefetch] 시작 — 전체 {len(sns)}개 | 캐시 {cached_count}개 | "
        f"신규 쿼리 {len(uncached)}개"
    )

    try:
        for i, sn in enumerate(uncached, 1):
            logger.info(f"[Prefetch] [{i}/{len(uncached)}] {sn} 쿼리 중...")
            try:
                qr = await query_runner.run(sn)
                if qr.success:
                    result["queried"] += 1
                    logger.info(f"[Prefetch] [{sn}] 완료 → {qr.csv_path}")
                    if qr.csv_path:
                        _csv_to_xlsx(qr.csv_path)
                else:
                    result["failed"] += 1
                    result["failed_sns"].append(sn)
                    logger.warning(f"[Prefetch] [{sn}] 실패: {qr.error}")
            except Exception as e:
                result["failed"] += 1
                result["failed_sns"].append(sn)
                logger.error(f"[Prefetch] [{sn}] 오류: {e}")

            await asyncio.sleep(3)  # 서버 부하 분산

        _status["last_result"] = result
        logger.info(
            f"[Prefetch] 완료 — 쿼리 성공 {result['queried']}개 | "
            f"실패 {result['failed']}개"
        )
        return result

    except Exception as e:
        _status["error"] = str(e)
        logger.error(f"[Prefetch] 실행 오류: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
    finally:
        _status["running"] = False
        _status["last_run"] = datetime.now().isoformat()


# ── 전체 파이프라인 (Qings → 엑셀 → SN 추출 → 쿼리) ─────────────────────────
async def run_daily_prefetch() -> dict:
    """Qings에서 SN 수집 후 사전 쿼리 전체 파이프라인을 실행합니다."""
    from app.prefetch.qings_scraper import scrape_qings_excel

    if _status["running"]:
        return {"status": "already_running"}

    logger.info("[Prefetch] 일일 사전 쿼리 시작")

    # 1. Qings 엑셀 다운로드
    excel_path = await scrape_qings_excel(settings.CSV_DOWNLOAD_PATH)
    if not excel_path:
        _status["error"] = "Qings 엑셀 다운로드 실패"
        return {"status": "error", "error": _status["error"]}

    # 2. SN 추출
    sns = extract_sns_from_excel(excel_path)
    if not sns:
        return {"status": "error", "error": f"SN 추출 실패 — 열 이름 확인 필요: {settings.QINGS_SN_COLUMN}"}

    # 3. 사전 쿼리 실행
    return await run_prefetch_for_sns(sns)
