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


# ── SN 추출 ───────────────────────────────────────────────────────────────────
def extract_sns_from_excel(excel_path: str, sn_column: str | None = None) -> list[str]:
    """Qings 엑셀에서 SN 목록을 추출합니다.

    증상명(CV열) 필터: 통화/수화/송화/데이터 접속 관련 행만 포함.
    SN 추출: 제조번호(단축)(AS열), 중복 제거.
    """
    import openpyxl

    if sn_column is None:
        sn_column = settings.QINGS_SN_COLUMN

    symptom_col  = settings.QINGS_SYMPTOM_COLUMN
    keywords     = settings.QINGS_SYMPTOM_KEYWORDS

    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
    ws = wb.active

    headers = [
        str(cell.value).strip() if cell.value is not None else ""
        for cell in next(ws.iter_rows(max_row=1))
    ]

    if sn_column not in headers:
        logger.warning(f"[Prefetch] SN 열 '{sn_column}' 없음. 헤더: {headers[:10]}")
        wb.close()
        return []

    sn_idx      = headers.index(sn_column)
    symptom_idx = headers.index(symptom_col) if symptom_col in headers else None

    if symptom_idx is None:
        logger.warning(f"[Prefetch] 증상명 열 없음 — 필터 없이 전체 SN 추출")

    seen: set[str] = set()
    sns:  list[str] = []
    skipped = 0

    for row in ws.iter_rows(min_row=2, values_only=True):
        # 증상명 필터
        if symptom_idx is not None:
            symptom = str(row[symptom_idx]).strip() if symptom_idx < len(row) and row[symptom_idx] else ""
            if not any(kw in symptom for kw in keywords):
                skipped += 1
                continue

        val = row[sn_idx] if sn_idx < len(row) else None
        if val:
            sn = str(val).strip().upper()
            if sn and sn not in seen:
                seen.add(sn)
                sns.append(sn)

    wb.close()
    logger.info(f"[Prefetch] SN {len(sns)}개 추출 (증상 필터 통과 / {skipped}개 제외)")
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
