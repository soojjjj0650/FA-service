"""
통화품질 분석서비스 - FastAPI 메인 애플리케이션

엔드포인트:
  GET  /                          → 챗봇 UI (HTML)
  GET  /batch                     → 배치 쿼리 UI (HTML, 최대 5개 SN 동시 실행)
  POST /api/query                 → SN 조회 (REST, 동기 응답)
  POST /api/batch-query           → 최대 5개 SN 동시 쿼리 + CSV 다운로드 (비동기 Job)
  GET  /api/batch-status/{job_id} → 배치 Job 진행 상태 폴링
  WS   /ws/chat                   → SN 조회 (WebSocket, 실시간 진행 상태)
  GET  /api/status                → 브라우저 풀 상태 확인
  POST /api/session/reset         → 세션 수동 초기화
  POST /message                   → Knox Messenger 수신 (공식 스펙 URL)
  POST /api/knox/webhook          → Knox Messenger 수신 (구 URL, /message 로 포워딩)
  POST /webhook                   → 챗봇 Builder Adaptive Card 제출 수신 (SN 조회)
  POST /api/test-result           → Mock 결과 카드 즉시 반환 (챗봇 카드 형식 테스트용)
  GET  /api/jobs                  → 현재 활성 Job 목록 (디버그용)
  POST /api/prefetch/trigger      → 사전 쿼리 수동 실행 (SN 목록 또는 Qings 전체)
  GET  /api/prefetch/status       → 사전 쿼리 실행 상태 확인
  GET  /api/prefetch/cache        → 캐시된 SN 목록 조회
"""

import asyncio
import logging
import re
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Windows에서 Playwright가 ProactorEventLoop를 요구
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import httpx

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, UploadFile, File, Form
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.analysis.runner import generate_analysis_html
from pydantic import BaseModel, field_validator

from app.config import settings
from app.scraper.browser_pool import browser_pool
from app.scraper.query_runner import query_runner
from app.scraper.session_manager import session_manager
from app.scraper.station_scraper import station_scraper
from app.processor.data_processor import data_processor, ProcessedData
from app.agent.agent_client import agent_client

# ─── 로깅 설정 ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _parse_log_to_rows(log_path: str) -> list[dict]:
    """LOG 파일(DATE TIME FEATURE\t{JSON} 형식)을 data_processor용 rows로 변환"""
    import json as _json
    content = None
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr", "latin-1"):
        try:
            with open(log_path, encoding=enc) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    if not content:
        return []
    rows = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        tabs = line.split('\t')
        date = time_ = feature = json_str = ''
        if len(tabs) >= 3:
            dt = tabs[0].strip().split()
            date = dt[0] if dt else ''
            time_ = dt[1] if len(dt) > 1 else ''
            feature = tabs[1].strip()
            json_str = '\t'.join(tabs[2:]).strip()
        elif len(tabs) == 2:
            dt = tabs[0].strip().split()
            date = dt[0] if dt else ''
            time_ = dt[1] if len(dt) > 1 else ''
            feature = ' '.join(dt[2:]) if len(dt) > 2 else ''
            json_str = tabs[1].strip()
        else:
            bi = line.find('{')
            if bi < 0:
                continue
            pre = line[:bi].strip().split()
            date = pre[0] if pre else ''
            time_ = pre[1] if len(pre) > 1 else ''
            feature = ' '.join(pre[2:]) if len(pre) > 2 else ''
            json_str = line[bi:].strip()
        if not date or not feature or not json_str:
            continue
        try:
            _json.loads(json_str)
        except Exception:
            continue
        rows.append({'Date': date, 'Time': time_, 'feature': feature, 'custom_value': json_str})
    logger.info(f"[LOG 파서] {log_path} → {len(rows)}행 변환")
    return rows


# ─── FastAPI 앱 ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="통화품질 분석서비스",
    description="단말기 SN 기반 통화품질 분석서비스",
    version="1.0.0",
)


# ─── ASGI 레벨 요청 로깅 미들웨어 ────────────────────────────────────────────
# ※ body는 미들웨어에서 읽지 않음 (Starlette BaseHTTPMiddleware 스트림 충돌 방지)
#    body 내용은 각 엔드포인트 핸들러에서 직접 로깅합니다.
@app.middleware("http")
async def log_every_request(request: Request, call_next):
    logger.info(
        f"[HTTP] 수신 | {request.method} {request.url.path} "
        f"| content-type={request.headers.get('content-type', '-')}"
    )
    try:
        response = await call_next(request)
        logger.info(f"[HTTP] 응답 | {request.method} {request.url.path} → {response.status_code}")
        return response
    except Exception as exc:
        logger.error(f"[HTTP] 미들웨어 예외 | {request.method} {request.url.path} | {type(exc).__name__}: {exc}", exc_info=True)
        raise


FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


# ─── 전역 예외 핸들러 ────────────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """422 Pydantic 유효성 오류 — 수신된 body를 로그에 기록합니다."""
    body = await request.body()
    logger.error(f"[Webhook] 422 유효성 오류 | path={request.url.path} | body={body.decode(errors='replace')} | errors={exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """500 예상치 못한 오류 — 경로·오류를 로그에 기록합니다."""
    logger.error(f"[Server] 500 내부 오류 | path={request.url.path} | {type(exc).__name__}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "내부 서버 오류가 발생했습니다."})


# ─── 배치 Job 저장소 (메모리) ─────────────────────────────────────────────────
# job_id → {"status": str, "sns": list, "results": list, "progress": dict}
_batch_jobs: dict[str, dict] = {}

# ─── 챗봇 Job 저장소 (메모리) ─────────────────────────────────────────────────
# job_id → {"status": str, "sn": str, "ai_response": str, "feature_summary": str, "error": str}
_chatbot_jobs: dict[str, dict] = {}


# ─── 수명 주기 이벤트 ─────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await browser_pool.startup()
    logger.info("코드 매핑 로드 시작...")
    try:
        from app.processor.code_mappings import load_code_mappings
        load_code_mappings()
    except Exception as e:
        logger.error(f"코드 매핑 로드 중 오류: {e}", exc_info=True)

    # CDN 캐시 사전 다운로드 (Chart.js, Leaflet)
    try:
        from app.analysis.runner import _get_chartjs, _fetch_and_cache, _LEAFLET_JS_URL, _LEAFLET_JS_CACHE_PATH, _LEAFLET_CSS_URL, _LEAFLET_CSS_CACHE_PATH
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _get_chartjs)
        await loop.run_in_executor(None, _fetch_and_cache, _LEAFLET_JS_URL, _LEAFLET_JS_CACHE_PATH, "Leaflet.js")
        await loop.run_in_executor(None, _fetch_and_cache, _LEAFLET_CSS_URL, _LEAFLET_CSS_CACHE_PATH, "Leaflet.css")
        logger.info("CDN 캐시 준비 완료 (Chart.js, Leaflet)")
    except Exception as e:
        logger.warning(f"CDN 캐시 다운로드 실패 (오프라인 환경에서 계속): {e}")

    if settings.PREFETCH_ENABLED:
        asyncio.create_task(_prefetch_scheduler())
        logger.info("[Scheduler] 사전 쿼리 스케줄러 시작 (평일 09:00)")

    if settings.LOGIN_AUTO_ENABLED:
        asyncio.create_task(_login_scheduler())
        logger.info("[Scheduler] 자동 로그인 스케줄러 시작 (매일 09:00)")

    if settings.MAIL_ENABLED:
        asyncio.create_task(_mail_scheduler())
        logger.info(f"[Scheduler] 메일 다운로드 스케줄러 시작 (매일 {settings.MAIL_SCHEDULE_HOUR:02d}:00)")

    logger.info("통화품질 분석서비스 시작")


@app.on_event("shutdown")
async def shutdown():
    await browser_pool.shutdown()
    await agent_client.close()
    logger.info("통화품질 분석서비스 종료")


# ─── 요청/응답 스키마 ─────────────────────────────────────────────────────────
class SNQueryRequest(BaseModel):
    sn: str
    @field_validator("sn")
    @classmethod
    def validate_sn(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("SN을 입력해 주세요.")
        if len(v) > 50:
            raise ValueError("SN이 너무 깁니다 (최대 50자).")
        if not re.match(r'^[A-Z0-9\-]+$', v):
            raise ValueError("SN은 영문, 숫자, 하이픈(-)만 사용 가능합니다.")
        return v


class BatchSNRequest(BaseModel):
    sns: list[str]

    @field_validator("sns")
    @classmethod
    def validate_sns(cls, v: list[str]) -> list[str]:
        cleaned = [sn.strip().upper() for sn in v if sn.strip()]
        if not cleaned:
            raise ValueError("SN을 최소 1개 입력해 주세요.")
        if len(cleaned) > 5:
            raise ValueError("SN은 최대 5개까지 입력 가능합니다.")
        for sn in cleaned:
            if len(sn) > 50:
                raise ValueError(f"SN이 너무 깁니다: {sn}")
            if not re.match(r'^[A-Z0-9\-]+$', sn):
                raise ValueError(f"SN은 영문, 숫자, 하이픈(-)만 사용 가능합니다: {sn}")
        return cleaned


# ─── REST 엔드포인트 ──────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    """챗봇 UI를 반환합니다."""
    html_file = FRONTEND_DIR / "index.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>통화품질 분석서비스</h1><p>frontend/index.html을 확인하세요.</p>")


@app.get("/batch", response_class=HTMLResponse)
async def batch_ui():
    """배치 쿼리 UI (최대 5개 SN 동시 실행)를 반환합니다."""
    html_file = FRONTEND_DIR / "batch.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Batch Query</h1><p>frontend/batch.html을 확인하세요.</p>")


@app.post("/api/query")
async def query_sn(request: SNQueryRequest):
    """
    SN을 받아 단말기 정보를 조회하고 AI 분석 결과를 반환합니다.

    챗봇에서 호출 시:
      - 즉시 202 접수 응답 반환 (60초 timeout 대응)
      - 백그라운드에서 통화품질 분석 후 완료 시 회사 챗봇 웹훅으로 결과 push
    """
    if not settings.CHATBOT_WEBHOOK_URL:
        raise HTTPException(status_code=503, detail="CHATBOT_WEBHOOK_URL이 설정되지 않았습니다.")

    asyncio.create_task(_run_and_push(request.sn))
    return JSONResponse(
        status_code=202,
        content={
            "message": f"SN [{request.sn}] 조회가 접수되었습니다. 완료 후 채팅방으로 결과를 전송합니다.",
            "sn": request.sn,
        },
    )


async def _prefetch_scheduler() -> None:
    """평일 오전 09:00 자동 사전 쿼리 스케줄러."""
    while True:
        now = datetime.now()
        # 다음 평일 09:00 계산
        target = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now >= target or now.weekday() >= 5:
            # 오늘 9시가 지났거나 주말이면 다음 평일 09:00으로
            days_ahead = 1
            while True:
                candidate = target + timedelta(days=days_ahead)
                if candidate.weekday() < 5:
                    target = candidate
                    break
                days_ahead += 1

        wait_sec = (target - datetime.now()).total_seconds()
        logger.info(
            f"[Scheduler] 다음 사전 쿼리: {target.strftime('%Y-%m-%d %H:%M')} "
            f"(대기 {wait_sec/3600:.1f}h)"
        )
        await asyncio.sleep(max(wait_sec, 1))

        logger.info("[Scheduler] 일일 사전 쿼리 시작")
        try:
            from app.prefetch.prefetch_runner import run_daily_prefetch
            await run_daily_prefetch()
        except Exception as e:
            logger.error(f"[Scheduler] 사전 쿼리 오류: {e}", exc_info=True)


async def _login_scheduler() -> None:
    """매일 09:00 자동 로그인 스케줄러 (ID/PW 입력 + Bio 버튼 클릭까지 자동)."""
    while True:
        now = datetime.now()
        target = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now >= target:
            target = target + timedelta(days=1)

        wait_sec = (target - datetime.now()).total_seconds()
        logger.info(f"[LoginScheduler] 다음 자동 로그인: {target.strftime('%Y-%m-%d %H:%M')} (대기 {wait_sec/3600:.1f}h)")
        await asyncio.sleep(max(wait_sec, 1))

        logger.info("[LoginScheduler] 자동 로그인 시작 (Bio 인증 대기 중...)")
        try:
            from scripts.manual_login import manual_login
            await manual_login()
            logger.info("[LoginScheduler] 자동 로그인 완료")
        except Exception as e:
            logger.error(f"[LoginScheduler] 자동 로그인 실패: {e}", exc_info=True)


def _prevent_sleep() -> bool:
    """Windows 절전 방지 활성화. 비Windows 또는 실패 시 False 반환."""
    try:
        import ctypes
        ES_CONTINUOUS      = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        return True
    except Exception:
        return False


def _restore_sleep() -> None:
    """Windows 절전 방지 해제."""
    try:
        import ctypes
        ES_CONTINUOUS = 0x80000000
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except Exception:
        pass


async def _mail_and_query_pipeline() -> dict:
    """FA 미결건 메일 다운로드 → SN 추출 → Superset 쿼리 → CSV 저장 전체 파이프라인."""
    import os
    from app.scraper.mail_downloader import download_mail_attachments
    from app.prefetch.prefetch_runner import extract_sns_from_excel

    # 파이프라인 실행 중 Windows 절전 방지
    sleep_prevented = _prevent_sleep()
    if sleep_prevented:
        logger.info("[MailPipeline] 절전 방지 활성화")

    result = {"files": [], "sns": [], "query_results": []}

    # 1. 메일 첨부파일 다운로드
    logger.info("[MailPipeline] 메일 다운로드 시작...")
    files = await download_mail_attachments()
    result["files"] = files
    logger.info(f"[MailPipeline] 다운로드 완료 — {len(files)}개 파일")

    if not files:
        logger.info("[MailPipeline] 다운로드된 파일 없음 — 쿼리 생략")
        if sleep_prevented:
            _restore_sleep()
        return result

    # 2. 엑셀에서 SN 추출
    sns: list[str] = []
    for f in files:
        try:
            extracted = extract_sns_from_excel(f)
            logger.info(f"[MailPipeline] {os.path.basename(f)} → SN {len(extracted)}개: {extracted[:5]}")
            for sn in extracted:
                if sn and sn not in sns:
                    sns.append(sn)
        except Exception as e:
            logger.warning(f"[MailPipeline] SN 추출 실패 ({f}): {e}")

    result["sns"] = sns
    logger.info(f"[MailPipeline] 총 SN {len(sns)}개 추출")

    if not sns:
        logger.warning("[MailPipeline] 추출된 SN 없음 — 쿼리 생략")
        if sleep_prevented:
            _restore_sleep()
        return result

    # 3. SN별 Superset 쿼리 실행 (BATCH_CONCURRENCY 제한)
    sem = asyncio.Semaphore(settings.BATCH_CONCURRENCY)

    async def _query_one(sn: str) -> dict:
        async with sem:
            logger.info(f"[MailPipeline] [{sn}] 쿼리 시작")
            try:
                qr = await query_runner.run(sn)
                status = "success" if qr.success else "fail"
                logger.info(f"[MailPipeline] [{sn}] {status} | csv={qr.csv_path}")
                return {"sn": sn, "success": qr.success, "csv_path": qr.csv_path, "error": qr.error}
            except Exception as e:
                logger.error(f"[MailPipeline] [{sn}] 쿼리 오류: {e}")
                return {"sn": sn, "success": False, "error": str(e)}

    query_results = await asyncio.gather(*[_query_one(sn) for sn in sns])
    result["query_results"] = list(query_results)

    success_cnt = sum(1 for r in query_results if r.get("success"))
    logger.info(f"[MailPipeline] 쿼리 완료 — {success_cnt}/{len(sns)}개 성공")

    if sleep_prevented:
        _restore_sleep()
        logger.info("[MailPipeline] 절전 방지 해제")

    return result


async def _mail_scheduler() -> None:
    """매일 MAIL_SCHEDULE_HOUR:MAIL_SCHEDULE_MINUTE에 메일→SN→쿼리 파이프라인 실행."""
    while True:
        now = datetime.now()
        target = now.replace(
            hour=settings.MAIL_SCHEDULE_HOUR,
            minute=settings.MAIL_SCHEDULE_MINUTE,
            second=0, microsecond=0,
        )
        if now >= target:
            target = target + timedelta(days=1)

        wait_sec = (target - datetime.now()).total_seconds()
        logger.info(
            f"[MailScheduler] 다음 실행: {target.strftime('%Y-%m-%d %H:%M')} "
            f"(대기 {wait_sec/3600:.1f}h)"
        )
        await asyncio.sleep(max(wait_sec, 1))

        logger.info("[MailScheduler] 메일→쿼리 파이프라인 시작")
        try:
            await _mail_and_query_pipeline()
        except Exception as e:
            logger.error(f"[MailScheduler] 오류: {e}", exc_info=True)


async def _run_and_push(sn: str) -> None:
    """통화품질 분석 전체 파이프라인 실행 후 회사 챗봇 웹훅으로 결과 push."""
    try:
        # 1. SQL 쿼리
        query_result = await query_runner.run(sn)
        if not query_result.success:
            msg = (
                "세션이 만료되었습니다. 관리자에게 재로그인을 요청해 주세요."
                if query_result.session_expired
                else (query_result.error or "데이터 조회에 실패했습니다.")
            )
            await _push_to_chatbot(f"[{sn}] 오류: {msg}")
            return

        # 2. 데이터 가공
        processed = data_processor.process(query_result)
        if processed.error and not processed.summary_text:
            await _push_to_chatbot(f"[{sn}] 오류: {processed.error}")
            return

        # 3. AI 분석
        ai_response = await agent_client.analyze(processed)

        await _push_to_chatbot(ai_response)
        logger.info(f"[Push] [{sn}] 챗봇 웹훅 전송 완료")

    except Exception as e:
        logger.error(f"[Push] [{sn}] 파이프라인 오류: {e}")
        await _push_to_chatbot(f"[{sn}] 처리 중 오류가 발생했습니다: {e}")


async def _push_to_chatbot(text: str) -> None:
    """회사 챗봇 웹훅 URL로 결과 텍스트를 POST합니다."""
    try:
        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            resp = await client.post(settings.CHATBOT_WEBHOOK_URL, json={"text": text})
            resp.raise_for_status()
    except Exception as e:
        logger.error(f"[Push] 챗봇 웹훅 호출 실패: {e}")


# ─── 표 컬럼 그룹 정의 (GROUPED_TABLE_DISPLAY=true 시 사용) ──────────────────
# 헤더 컬럼 집합 → [(그룹명, [컬럼명, ...])] 매핑
_TABLE_GROUPS: list[tuple[frozenset, list[tuple[str, list[str]]]]] = [
    (
        frozenset(["PLMN","ACT","TAC","LAC","PCI","DLCh","Band",
                   "UBMT","RSMT","RNMT","DBMT","ECNT","RSRP","RSCP","SINR","BLER"]),
        [
            ("위치", ["PLMN", "ACT", "TAC", "LAC", "PCI", "DLCh", "Band"]),
            ("횟수", ["UBMT", "RSMT", "RNMT", "DBMT", "ECNT"]),
            ("신호", ["RSRP", "RSCP", "SINR", "BLER"]),
        ],
    ),
]


def _find_groups(headers: list[str]):
    """헤더 목록에 맞는 그룹 정의를 찾아 반환. 없으면 None."""
    h_set = frozenset(headers)
    for key_set, groups in _TABLE_GROUPS:
        if h_set >= key_set or h_set <= key_set:  # 부분 일치도 허용
            return groups
    return None


def _format_row_grouped(
    headers: list[str],
    cells: list[str],
    groups: list[tuple[str, list[str]]],
    num: str,
) -> str:
    """데이터 행을 그룹별 여러 줄로 포맷."""
    col_map = {h: (cells[i] if i < len(cells) else "") for i, h in enumerate(headers)}
    lines = []
    for g_name, g_cols in groups:
        pairs = [f"{c}:{col_map[c]}" for c in g_cols if col_map.get(c)]
        if pairs:
            prefix = f"{num} [{g_name}]" if not lines else f"   [{g_name}]"
            lines.append(prefix + " " + " ".join(pairs))
    return "\n".join(lines)


def _normalize_md_tables(text: str) -> str:
    """AI 응답 내 마크다운 표의 열 너비를 헤더 기준으로 맞춰 정렬합니다."""
    lines = text.splitlines()
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("|") and "|" in line:
            table_block: list[str] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_block.append(lines[i])
                i += 1
            data_lines = [l for l in table_block
                          if not re.match(r"^\s*\|[\s\-:]+\|", l)]
            if len(data_lines) >= 2:
                all_rows = [
                    [v.strip() for v in l.strip().strip("|").split("|")]
                    for l in data_lines
                ]
                n_cols = max(len(r) for r in all_rows)
                for r in all_rows:
                    while len(r) < n_cols:
                        r.append("")
                widths = [max(len(r[j]) for r in all_rows) for j in range(n_cols)]

                def fmt(row: list[str]) -> str:
                    return "| " + " | ".join(f"{row[j]:<{widths[j]}}" for j in range(n_cols)) + " |"

                result.append(fmt(all_rows[0]))
                result.append("|" + "|".join("-" * (w + 2) for w in widths) + "|")
                for row in all_rows[1:]:
                    result.append(fmt(row))
            else:
                result.extend(table_block)
        else:
            result.append(line)
            i += 1
    return "\n".join(result)


def _strip_markdown(text: str) -> str:
    """AI 응답의 마크다운 헤딩·굵게 기호를 제거하고 제목을 기호로 강조합니다."""
    lines = []
    for line in text.splitlines():
        if line.startswith("###"):
            lines.append(f"\n▶ {line.lstrip('#').strip()}")
        elif line.startswith("##"):
            lines.append(f"\n◆ {line.lstrip('#').strip()}")
        elif line.startswith("#"):
            lines.append(f"\n■ {line.lstrip('#').strip()}")
        else:
            lines.append(line)
    result = "\n".join(lines)
    result = result.replace("**", "")
    # 마크다운 수평선 (---, ***, ___) 줄 자체 제거
    result = "\n".join(
        l for l in result.splitlines()
        if not re.match(r'^\s*[-*_]{3,}\s*$', l)
    )
    # 연속 빈 줄 2개 이상 → 1개로 축소
    result = re.sub(r'\n{3,}', '\n\n', result)
    # 마크다운 표 열 너비 정규화
    result = _normalize_md_tables(result)
    return result


async def _push_card_to_chatroom(job: dict) -> None:
    return  # botbuilder push 비활성화

    chat_room_id = job.get("chatRoomId")
    user_id = job.get("userId")
    sn = job.get("sn", "")
    status = job.get("status")

    if not chat_room_id and not user_id:
        logger.warning(f"[Push] chatRoomId/userId 없음 - 자동 push 불가 (SN: {sn})")
        return

    # Samsung chatbot Builder push payload
    # - 앱카드 템플릿 : ${body.title} / ${body.ai_result} / ${body.station_info}
    if status == "done" and job.get("no_data"):
        days_val = job.get('query_days') or settings.QUERY_LOOKBACK_DAYS
        payload = {
            "chatRoomId":    chat_room_id,
            "userId":        user_id,
            "title":         f"[SN: {sn}] 통화품질 분석 결과",
            "info_analysis": "",
            "ai_result":     f"최근 {days_val}일간 조회되는 데이터가 없습니다.",
            "station_info":  "",
            "analysis_url":  "",
        }
    elif status == "done":
        ai_text = _strip_markdown(job.get('ai_response', ''))
        station_text = job.get('station_text', '')
        feature_tables = job.get('feature_tables') or {}
        feature_summary = job.get('feature_summary', '')
        info_analysis = _feature_tables_to_text(feature_tables, feature_summary, job.get('query_days'))

        # 단말정보 헤더를 info_analysis 맨 위에 추가
        _PLMN_DISP = {"45005": "SKT", "45008": "KT", "45002": "KT", "45004": "KT",
                      "45006": "LGU+", "45018": "LGU+", "45010": "LGU+"}
        plmn = job.get('plmn', '')
        operator_disp = _PLMN_DISP.get(plmn, plmn or '-')
        device_model = job.get('device_model', '') or '-'
        query_days_val = job.get('query_days') or settings.QUERY_LOOKBACK_DAYS
        device_header = f"[ 단말정보 ] 최근 {query_days_val}일간\n\n사업자: {operator_disp} | 모델: {device_model}\n\n"
        info_analysis = device_header + info_analysis

        analysis_url = job.get("analysis_url") or ""
        payload = {
            "chatRoomId":    chat_room_id,
            "userId":        user_id,
            "title":         f"[SN: {sn}] 통화품질 분석 결과",
            "info_analysis": info_analysis,
            "ai_result":     ai_text,
            "station_info":  station_text,
            "analysis_url":  analysis_url,
        }
    else:
        payload = {
            "chatRoomId":   chat_room_id,
            "userId":       user_id,
            "title":        f"[SN: {sn}] 통화품질 분석 오류",
            "ai_result":    job.get('error', '처리 중 오류가 발생했습니다.'),
            "station_info": "",
        }

    headers = {"Content-Type": "application/json"}
    if settings.CHATBOT_PUSH_API_KEY:
        headers["x-api-key"] = settings.CHATBOT_PUSH_API_KEY

    # URL 끝에 chatRoomId 추가: https://botbuilder.samsung.net/webhook/fa.service/{chatRoomId}
    push_url = settings.CHATBOT_PUSH_URL.rstrip("/")
    if chat_room_id:
        push_url = f"{push_url}/{chat_room_id}"

    try:
        async with httpx.AsyncClient(timeout=30, verify=False, trust_env=False) as client:
            resp = await client.post(push_url, json=payload, headers=headers)
            logger.info(
                f"[Push] 결과 push 완료 | SN={sn} | url={push_url} | status={resp.status_code}"
            )
            if resp.status_code >= 400:
                logger.warning(f"[Push] push 응답 오류: {resp.status_code} - {resp.text[:200]}")
    except Exception as e:
        logger.error(f"[Push] 결과 push 실패 (SN: {sn}): {type(e).__name__}: {e}", exc_info=True)


@app.post("/api/batch-query")
async def batch_query(request: BatchSNRequest):
    """
    최대 5개의 SN에 대해 Superset SQL 쿼리를 동시에 실행하고 CSV를 다운로드합니다.

    즉시 job_id를 반환하며, 진행 상태는 GET /api/batch-status/{job_id}로 폴링하세요.
    각 SN의 CSV는 설정된 다운로드 경로에 {SN}_inputdata.csv 로 저장됩니다.
    """
    job_id = str(uuid.uuid4())
    _batch_jobs[job_id] = {
        "status": "pending",
        "sns": request.sns,
        "progress": {sn: "대기 중" for sn in request.sns},
        "results": [],
        "download_dir": settings.CSV_DOWNLOAD_PATH,
    }

    # asyncio.create_task: 현재 이벤트 루프에 즉시 등록 → request handler가 바로 반환
    asyncio.create_task(_run_batch_job(job_id, request.sns))

    return {
        "job_id": job_id,
        "sns": request.sns,
        "message": f"{len(request.sns)}개 SN 쿼리 시작. /api/batch-status/{job_id} 로 진행 상태 확인.",
    }


@app.get("/api/batch-status/{job_id}")
async def batch_status(job_id: str):
    """배치 Job의 현재 진행 상태를 반환합니다."""
    job = _batch_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    return job


async def _run_batch_job(job_id: str, sns: list[str]) -> None:
    """백그라운드에서 모든 SN 쿼리를 동시에 실행합니다."""
    job = _batch_jobs[job_id]
    job["status"] = "running"

    async def run_one(sn: str):
        async def on_progress(msg: str):
            job["progress"][sn] = msg
            logger.info(f"[Batch {job_id}] [{sn}] {msg}")

        result = await query_runner.run(sn, progress_callback=on_progress)
        return {
            "sn": sn,
            "success": result.success,
            "csv_path": result.csv_path,
            "error": result.error,
            "session_expired": result.session_expired,
        }

    try:
        tasks = [run_one(sn) for sn in sns]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        job["results"] = [
            r if isinstance(r, dict) else {"sn": sns[i], "success": False, "error": str(r)}
            for i, r in enumerate(results)
        ]
        job["status"] = "completed"
        logger.info(f"[Batch {job_id}] 완료 - {len(job['results'])}건")

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        logger.error(f"[Batch {job_id}] 배치 실행 오류: {e}")


@app.get("/api/status")
async def status():
    """브라우저 풀 및 세션 상태를 반환합니다."""
    sess = session_manager.session_info()
    return {
        "active_browsers": browser_pool.active_count,
        "max_browsers": browser_pool.max_size,
        "available_slots": browser_pool.max_size - browser_pool.active_count,
        "session": sess,
    }


@app.post("/api/session/reset")
async def reset_session():
    """
    수동 재로그인 후 세션 복구를 알립니다.
    scripts/manual_login.py 실행 완료 후 이 API를 호출하세요.
    """
    session_manager.mark_refreshed()
    info = session_manager.session_info()
    return {
        "message": "세션 복구 완료. 정상적으로 조회가 가능합니다.",
        "session": info,
    }


class TestResultRequest(BaseModel):
    sn: str = "TEST-001"
    ai_response: Optional[str] = None
    feature_summary: Optional[str] = None


@app.post("/api/test-result")
async def test_result_card(request: TestResultRequest):
    """
    Mock 결과 Adaptive Card를 즉시 반환합니다.
    실제 Superset 조회 없이 챗봇 카드 형식을 테스트하는 용도입니다.

    챗봇 Builder 설정에서 이 엔드포인트를 호출해 카드 렌더링을 확인하세요.
    """
    sn = request.sn.strip().upper() or "TEST-001"
    ai_text = request.ai_response or (
        f"[TEST] SN [{sn}] 통화품질 분석 결과\n\n"
        "■ MUTE 이벤트 주요 발생 지역\n"
        "- PLMN: 45008 / ACT: LTE / TAC: 12345\n"
        "  PCI: 100, ECNT: 150건, RSRP: -105.3 dBm, SINR: 2.1 dB\n\n"
        "- PLMN: 45008 / ACT: LTE / TAC: 23456\n"
        "  PCI: 200, ECNT: 80건, RSRP: -98.7 dBm, SINR: 5.4 dB\n\n"
        "■ 종합 의견\n"
        "특정 셀(PCI 100, TAC 12345)에서 무음 이벤트가 집중 발생하고 있습니다. "
        "해당 기지국 파라미터 점검 및 핸드오버 설정 검토를 권장합니다."
    )
    feat_summary = request.feature_summary or "MUTE: 230건"
    card = _build_result_card(sn, ai_text, feat_summary)
    logger.info(f"[TestResult] Mock 결과 카드 반환 - SN: {sn}")
    return JSONResponse(card)


@app.get("/api/appcard")
async def get_appcard(sn: str = "", userId: str = ""):
    """
    Samsung chatbot Builder 앱카드 API 연계 엔드포인트.

    App Card 설정에서 이 URL을 지정하면 카드 표시 시 동적으로 데이터를 가져옵니다.

    Query params:
      sn     : 조회할 단말기 SN (있으면 해당 SN의 최신 완료 Job 결과 반환)
      userId : 사용자 ID (sn 없을 때 해당 user의 최신 Job 결과 반환)

    반환:
      - 완료된 분석 결과 → _build_result_card() Adaptive Card JSON
      - 분석 중       → 처리중 안내 카드
      - 결과 없음     → SN 입력 폼 카드
    """
    sn = sn.strip().upper()
    userId = userId.strip()

    # SN 또는 userId로 최신 완료 Job 탐색 (최신 순)
    matched_job = None
    for job in reversed(list(_chatbot_jobs.values())):
        if sn and job.get("sn", "").upper() == sn:
            matched_job = job
            break
        if not sn and userId and job.get("userId") == userId:
            matched_job = job
            break

    if matched_job is None:
        return JSONResponse(_build_input_form_card())

    status = matched_job.get("status")
    job_sn = matched_job.get("sn", sn)

    if status == "done":
        card = _build_result_card(
            job_sn,
            matched_job.get("ai_response", ""),
            matched_job.get("feature_summary", ""),
            matched_job.get("station_entries"),
            matched_job.get("station_text", ""),
            matched_job.get("feature_tables"),
            matched_job.get("analysis_url", ""),
        )
        return JSONResponse(card)
    elif status == "error":
        return JSONResponse({
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.3",
            "body": [
                {"type": "TextBlock", "text": f"[{job_sn}] 통화품질 분석 오류",
                 "weight": "Bolder", "color": "Attention"},
                {"type": "TextBlock", "text": matched_job.get("error", "처리 중 오류 발생"),
                 "wrap": True, "color": "Attention"},
            ],
        })
    else:
        # pending / running
        return JSONResponse({
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.3",
            "body": [
                {"type": "TextBlock", "text": f"[{job_sn}] 통화품질 분석 진행 중",
                 "weight": "Bolder", "color": "Warning"},
                {"type": "TextBlock", "text": "분석이 완료되면 결과가 자동으로 표시됩니다.",
                 "wrap": True, "isSubtle": True},
            ],
        })


class PrefetchTriggerRequest(BaseModel):
    sns: Optional[list[str]] = None  # 비워두면 Qings에서 자동 수집


@app.post("/api/prefetch/trigger")
async def prefetch_trigger(request: PrefetchTriggerRequest):
    """
    사전 쿼리를 수동으로 실행합니다.
    - sns 미지정: Qings 사이트에서 SN 자동 수집 후 쿼리
    - sns 지정: 해당 SN 목록만 쿼리 (캐시 없는 것만)
    """
    from app.prefetch.prefetch_runner import run_daily_prefetch, run_prefetch_for_sns, get_status
    if get_status()["running"]:
        return JSONResponse(status_code=409, content={"detail": "이미 사전 쿼리가 실행 중입니다."})

    if request.sns:
        sns = [s.strip().upper() for s in request.sns if s.strip()]
        asyncio.create_task(run_prefetch_for_sns(sns))
        return {"message": f"{len(sns)}개 SN 사전 쿼리 시작", "sns": sns}
    else:
        asyncio.create_task(run_daily_prefetch())
        return {"message": "Qings 수집 → 사전 쿼리 시작 (백그라운드 실행)"}


@app.post("/api/mail/trigger")
async def mail_trigger():
    """FA 미결건 메일 다운로드 → SN 추출 → Superset 쿼리 전체 파이프라인을 즉시 실행합니다."""
    asyncio.create_task(_mail_and_query_pipeline())
    return {"status": "started", "message": "메일→SN 추출→쿼리 파이프라인이 백그라운드에서 시작되었습니다."}


@app.get("/api/prefetch/status")
async def prefetch_status():
    """사전 쿼리 실행 상태를 반환합니다."""
    from app.prefetch.prefetch_runner import get_status
    return get_status()


@app.get("/api/prefetch/cache")
async def prefetch_cache():
    """캐시된 SN 목록을 반환합니다."""
    from app.prefetch.cache_manager import list_cached_sns
    cached = list_cached_sns()
    return {
        "total": len(cached),
        "fresh": sum(1 for c in cached if c["fresh"]),
        "cache_max_age_hours": settings.CACHE_MAX_AGE_HOURS,
        "items": cached,
    }


@app.get("/api/jobs")
async def list_jobs():
    """
    현재 메모리에 있는 챗봇 Job 목록을 반환합니다 (디버그용).
    최근 10개의 Job 상태를 보여줍니다.
    """
    jobs_info = []
    for job_id, job in list(_chatbot_jobs.items())[-10:]:
        jobs_info.append({
            "job_id": job_id,
            "sn": job.get("sn"),
            "status": job.get("status"),
            "userId": job.get("userId"),
            "chatRoomId": job.get("chatRoomId"),
            "error": job.get("error"),
            "created_at": job.get("created_at"),
        })
    return {
        "total": len(_chatbot_jobs),
        "mock_mode": settings.MOCK_MODE,
        "push_url_set": bool(settings.CHATBOT_PUSH_URL),
        "jobs": list(reversed(jobs_info)),
    }


# ─── Knox Messenger 관리 엔드포인트 ──────────────────────────────────────────

@app.post("/api/knox/register")
async def knox_register_device():
    """
    Knox Messenger 초기 설정:
    1. Device ID 획득 (등록 API 호출)
    2. 대화방 생성 (최초 1회)

    결과는 data/knox_device_id.txt, data/knox_chatroom_id.txt에 저장되어 재사용됩니다.
    """
    if not settings.KNOX_MESSENGER_BASE_URL:
        raise HTTPException(status_code=400, detail="KNOX_MESSENGER_BASE_URL이 설정되지 않았습니다.")
    if not settings.KNOX_ACCESS_TOKEN:
        raise HTTPException(status_code=400, detail="KNOX_ACCESS_TOKEN이 설정되지 않았습니다.")
    if not settings.KNOX_RECEIVER_USER_ID:
        raise HTTPException(status_code=400, detail="KNOX_RECEIVER_USER_ID가 설정되지 않았습니다.")

    from app.messenger.knox_messenger import KnoxMessengerClient

    client = KnoxMessengerClient(
        base_url=settings.KNOX_MESSENGER_BASE_URL,
        access_token=settings.KNOX_ACCESS_TOKEN,
        system_id=settings.KNOX_SYSTEM_ID,
        device_id=settings.KNOX_DEVICE_ID,
        receiver_user_id=settings.KNOX_RECEIVER_USER_ID,
    )

    # 1. Device ID 강제 재등록 (항상 새로 등록)
    device_id = await client.register_device()
    if not device_id:
        raise HTTPException(status_code=502, detail="Device 등록 실패. 서버 로그를 확인하세요.")

    # 2. 대화방 생성 (register 시에는 항상 새로 생성)
    chatroom_id = await client.create_chatroom()
    if not chatroom_id:
        raise HTTPException(status_code=502, detail="대화방 생성 실패. 서버 로그를 확인하세요.")

    # 3. SN 입력 Adaptive Card 전송 (실패 시 텍스트 fallback)
    from app.messenger.knox_messenger import build_sn_input_card
    receive_url = settings.KNOX_RECEIVE_URL or (settings.KNOX_SERVER_URL + "/message" if settings.KNOX_SERVER_URL else f"{settings.BASE_URL}:{settings.PORT}/message")
    card_sent = await client.send_adaptive_card(chatroom_id, build_sn_input_card(receive_url))
    if not card_sent:
        await client.send_message(chatroom_id, _SN_GUIDE)

    logger.info(f"[Knox] 초기 설정 완료 | device_id={client.device_id} | chatroom_id={chatroom_id} | card_sent={card_sent}")
    return {
        "status": "ok",
        "device_id": client.device_id,
        "chatroom_id": chatroom_id,
        "card_sent": card_sent,
        "message": "Device ID 및 대화방 생성 완료. SN 입력 카드를 전송했습니다.",
    }


@app.get("/api/knox/bot-info")
async def knox_bot_info():
    """
    봇의 Knox 등록 정보를 반환합니다.
    bot_user_id == receiver_user_id 이면 4001 오류가 발생합니다.
    """
    from app.messenger.knox_messenger import KnoxMessengerClient
    client = KnoxMessengerClient(
        base_url=settings.KNOX_MESSENGER_BASE_URL,
        access_token=settings.KNOX_ACCESS_TOKEN,
        system_id=settings.KNOX_SYSTEM_ID,
        device_id=settings.KNOX_DEVICE_ID,
        receiver_user_id=settings.KNOX_RECEIVER_USER_ID,
    )
    resp_data = {}
    import requests as _req, urllib3 as _u3
    _u3.disable_warnings()
    url = f"{settings.KNOX_MESSENGER_BASE_URL}/messenger/contact/api/v2.0/device/o1/reg"
    headers = {
        "Authorization": f"Bearer {settings.KNOX_ACCESS_TOKEN}",
        "System-ID": settings.KNOX_SYSTEM_ID,
        "x-device-type": "relation",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        r = _req.get(url, headers=headers, verify=False, timeout=(15, 30))
        resp_data = r.json() if r.status_code < 400 else {"error": r.text[:300]}
    except Exception as e:
        resp_data = {"error": str(e)}

    bot_user_id = str(resp_data.get("userID", ""))
    same = (bot_user_id == settings.KNOX_RECEIVER_USER_ID and bot_user_id != "")
    return {
        "env": "prod" if "stage" not in settings.KNOX_MESSENGER_BASE_URL else "stage",
        "knox_base_url": settings.KNOX_MESSENGER_BASE_URL,
        "configured_device_id": settings.KNOX_DEVICE_ID,
        "configured_receiver_user_id": settings.KNOX_RECEIVER_USER_ID,
        "bot_user_id_from_registration": bot_user_id,
        "device_server_id": str(resp_data.get("deviceServerID", "")),
        "WARNING_same_as_receiver": same,
        "raw_response": resp_data,
    }


@app.get("/api/knox/search-user")
async def knox_search_user(keyword: str):
    """
    Knox Messenger에서 사용자 ID를 검색합니다.
    keyword: Samsung 계정 (예: sujin06.bae)
    """
    import requests as _req, urllib3 as _u3
    _u3.disable_warnings()
    headers = {
        "Authorization": f"Bearer {settings.KNOX_ACCESS_TOKEN}",
        "System-ID": settings.KNOX_SYSTEM_ID,
        "x-device-id": settings.KNOX_DEVICE_ID,
        "x-device-type": "relation",
        "Accept": "application/json",
    }
    results = []
    # Try multiple contact search endpoints
    endpoints = [
        f"{settings.KNOX_MESSENGER_BASE_URL}/messenger/contact/api/v2.0/contact/search?keyword={keyword}",
        f"{settings.KNOX_MESSENGER_BASE_URL}/messenger/contact/api/v2.0/contact?keyword={keyword}",
        f"{settings.KNOX_MESSENGER_BASE_URL}/messenger/contact/api/v2.0/user/search?keyword={keyword}",
    ]
    for url in endpoints:
        try:
            r = _req.get(url, headers=headers, verify=False, timeout=(15, 30))
            results.append({"url": url, "status": r.status_code, "body": r.text[:500]})
            if r.status_code < 400:
                break
        except Exception as e:
            results.append({"url": url, "error": str(e)})

    return {"keyword": keyword, "results": results}


@app.post("/api/knox/test-message")
async def knox_test_message():
    """캐시된 대화방에 텍스트 메시지를 전송해 연결을 확인합니다."""
    from app.messenger.knox_messenger import KnoxMessengerClient, _load_cached_device_id, _load_cached_chatroom_id
    chatroom_id = _load_cached_chatroom_id()
    if not chatroom_id:
        raise HTTPException(status_code=400, detail="대화방 없음. /api/knox/register 먼저 호출하세요.")
    client = KnoxMessengerClient(
        base_url=settings.KNOX_MESSENGER_BASE_URL,
        access_token=settings.KNOX_ACCESS_TOKEN,
        system_id=settings.KNOX_SYSTEM_ID,
        device_id=settings.KNOX_DEVICE_ID or _load_cached_device_id(),
        receiver_user_id=settings.KNOX_RECEIVER_USER_ID,
    )
    ok = await client.send_message(chatroom_id, "통화품질 분석서비스 연결 테스트 메시지입니다.")
    return {"chatroom_id": chatroom_id, "sent": ok}


@app.post("/api/knox/send-file")
async def knox_send_file(request: Request):
    """
    지정한 파일(PDF 등)을 Knox Messenger로 전송합니다.
    body: {"file_path": "C:\\...\\R3CW804XAD_analysis.pdf", "message": "선택 메시지"}
    """
    from app.messenger.knox_messenger import KnoxMessengerClient, _load_cached_device_id, _load_cached_chatroom_id
    import os as _os

    body = await request.json()
    file_path = (body.get("file_path") or "").strip()
    message   = body.get("message") or "통화품질 분석 결과 파일입니다."

    if not file_path:
        raise HTTPException(status_code=400, detail="file_path 필드가 필요합니다.")
    if not _os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {file_path}")

    chatroom_id = _load_cached_chatroom_id()
    if not chatroom_id:
        raise HTTPException(status_code=400, detail="대화방 없음. /api/knox/register 먼저 호출하세요.")

    client = KnoxMessengerClient(
        base_url=settings.KNOX_MESSENGER_BASE_URL,
        access_token=settings.KNOX_ACCESS_TOKEN,
        system_id=settings.KNOX_SYSTEM_ID,
        device_id=settings.KNOX_DEVICE_ID or _load_cached_device_id(),
        receiver_user_id=settings.KNOX_RECEIVER_USER_ID,
    )

    if not await client.ensure_device_id():
        raise HTTPException(status_code=502, detail="Knox Device ID 확보 실패.")

    upload_result = await client.upload_file(file_path)
    if not upload_result:
        raise HTTPException(status_code=502, detail="Knox 파일 업로드 실패.")
    file_url, file_size = upload_result

    filename = _os.path.basename(file_path)
    ok = await client.send_file_message(
        chatroom_id=chatroom_id,
        download_url=file_url,
        filename=filename,
        file_size=file_size,
        message_text=message,
    )
    return {"sent": ok, "file": filename, "chatroom_id": chatroom_id}


@app.post("/api/knox/send-analysis")
async def knox_send_analysis(request: Request):
    """
    SN을 입력받아 통화품질 분석 → PDF 생성 → Knox Messenger 전송을 수동으로 실행합니다.
    Knox 웹훅 없이도 테스트 가능.
    body: {"sn": "R3CUFHDJF"}
    """
    from app.messenger.knox_messenger import _load_cached_chatroom_id
    body = await request.json()
    sn = (body.get("sn") or "").strip().upper()
    if not sn:
        raise HTTPException(status_code=400, detail="sn 필드가 필요합니다.")

    chatroom_id = _load_cached_chatroom_id()
    if not chatroom_id:
        logger.info("[Knox] chatroom 캐시 없음 → 자동 register 시도")
        from app.messenger.knox_messenger import KnoxMessengerClient
        _client = KnoxMessengerClient(
            base_url=settings.KNOX_MESSENGER_BASE_URL,
            access_token=settings.KNOX_ACCESS_TOKEN,
            system_id=settings.KNOX_SYSTEM_ID,
            device_id=settings.KNOX_DEVICE_ID,
            receiver_user_id=settings.KNOX_RECEIVER_USER_ID,
        )
        if not await _client.ensure_device_id():
            raise HTTPException(status_code=502, detail="Knox Device 등록 실패. 서버 로그를 확인하세요.")
        chatroom_id = await _client.ensure_chatroom()
        if not chatroom_id:
            raise HTTPException(status_code=502, detail="Knox 대화방 생성 실패. 서버 로그를 확인하세요.")

    job_id = str(uuid.uuid4())
    _chatbot_jobs[job_id] = {
        "job_id":     job_id,
        "sn":         sn,
        "status":     "pending",
        "userId":     settings.KNOX_RECEIVER_USER_ID,
        "chatRoomId": chatroom_id,
        "created_at": time.time(),
        "source":     "knox",
    }
    async def _send_and_run():
        await _knox_reply(chatroom_id, f"[{sn}] 조회중입니다. 잠시 후 결과를 전송합니다.", with_card=False)
        await asyncio.sleep(2)
        await _run_knox_pipeline(job_id, sn)
    asyncio.create_task(_send_and_run())
    return {"status": "accepted", "job_id": job_id, "sn": sn, "chatroom_id": chatroom_id}


@app.get("/api/knox/status")
async def knox_status():
    """Knox Messenger 설정 상태를 확인합니다."""
    from app.messenger.knox_messenger import _load_cached_device_id, _load_cached_chatroom_id
    cached_device_id  = _load_cached_device_id()
    cached_chatroom_id = _load_cached_chatroom_id()
    return {
        "base_url": settings.KNOX_MESSENGER_BASE_URL or "(미설정)",
        "access_token_set": bool(settings.KNOX_ACCESS_TOKEN),
        "system_id": settings.KNOX_SYSTEM_ID,
        "device_id": settings.KNOX_DEVICE_ID or cached_device_id or "(없음 → /api/knox/register 호출 필요)",
        "chatroom_id": cached_chatroom_id or "(없음 → /api/knox/register 호출 필요)",
        "receiver_user_id": settings.KNOX_RECEIVER_USER_ID or "(미설정)",
        "enabled": settings.KNOX_MESSENGER_ENABLED,
    }


# ─── Knox Messenger 수신 웹훅 ─────────────────────────────────────────────────
# Knox 메시지 수신 스펙:
# POST /message
# {
#   "sender":       "7549538049580",   ← Knox 사용자 번호
#   "setTime":      "14239489989",     ← 전송 시각 (epoch ms)
#   "chatType":     "SINGLE",          ← SINGLE / GROUP
#   "chatroomId":   "239482039408",
#   "msgId":        12343234,
#   "msgType":      "TEXT",            ← TEXT / MEDIA / ADAPTIVE_CARD
#   "chatMsg":      "R3CUFHDJF",       ← 메시지 본문 (ADAPTIVE_CARD면 JSON 문자열)
#   "senderKnoxId": "aabbc"            ← Knox ID (응답 수신자 식별용)
# }

_SN_GUIDE = "분석할 단말기 SN을 입력해주세요.\n예) R3CUFHDJF\n여러 개는 쉼표로 구분: R3CUFHDJF, R3CUFHDJA"

async def _knox_reply(chatroom_id: str, text: str, with_card: bool = True) -> None:
    """Knox 채팅방에 텍스트 메시지를 전송합니다."""
    if not settings.KNOX_MESSENGER_BASE_URL or not settings.KNOX_ACCESS_TOKEN:
        return
    from app.messenger.knox_messenger import KnoxMessengerClient, _load_cached_device_id
    client = KnoxMessengerClient(
        base_url=settings.KNOX_MESSENGER_BASE_URL,
        access_token=settings.KNOX_ACCESS_TOKEN,
        system_id=settings.KNOX_SYSTEM_ID,
        device_id=settings.KNOX_DEVICE_ID or _load_cached_device_id(),
        receiver_user_id=settings.KNOX_RECEIVER_USER_ID,
    )
    if text:
        await client.send_message(chatroom_id, text)
    if with_card:
        from app.messenger.knox_messenger import build_sn_input_card
        receive_url = settings.KNOX_RECEIVE_URL or (settings.KNOX_SERVER_URL + "/message" if settings.KNOX_SERVER_URL else f"{settings.BASE_URL}:{settings.PORT}/message")
        card_ok = await client.send_adaptive_card(chatroom_id, build_sn_input_card(receive_url))
        if not card_ok:
            await client.send_message(chatroom_id, _SN_GUIDE)


async def _knox_parse_body(raw_text: str) -> dict:
    """Knox 수신 body 파싱 - 평문 JSON 또는 AES 암호화 body 모두 처리."""
    import json as _json

    # 1. 평문 JSON 시도
    try:
        data = _json.loads(raw_text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # 2. 암호화 body → getkeys로 복호화 시도
    if not raw_text.strip():
        return {}
    try:
        from app.messenger.knox_messenger import (
            KnoxMessengerClient, _load_cached_device_id, _aes256_decrypt
        )
        client = KnoxMessengerClient(
            base_url=settings.KNOX_MESSENGER_BASE_URL,
            access_token=settings.KNOX_ACCESS_TOKEN,
            system_id=settings.KNOX_SYSTEM_ID,
            device_id=settings.KNOX_DEVICE_ID or _load_cached_device_id(),
        )
        msg_key = await client.get_message_key()
        if msg_key and len(msg_key) >= 48:
            data = _aes256_decrypt(raw_text.strip(), msg_key[:32], msg_key[32:48])
            if data:
                logger.info(f"[Knox] body 복호화 성공: {str(data)[:300]}")
                return data
    except Exception as e:
        logger.error(f"[Knox] body 복호화 실패: {e}")

    return {}


async def _knox_handle_message(data: dict) -> JSONResponse:
    """Knox 수신 메시지 공통 처리 로직."""
    import json as _json

    msg_type    = str(data.get("msgType") or "").upper()
    chat_msg    = str(data.get("chatMsg") or "").strip()
    sender      = str(data.get("sender") or "").strip()
    chatroom_id = str(data.get("chatroomId") or "").strip()
    sender_knox = str(data.get("senderKnoxId") or "").strip()

    # raw chatMsg 전체 로그 (파일 수신 포맷 분석용)
    logger.info(f"[Knox] raw chatMsg(msgType={msg_type}): {chat_msg[:300]}")

    # Knox가 chatMsg 앞에 <!--{...} --> prefix를 붙이는 경우 → --> 이후 내용만 사용
    if '-->' in chat_msg:
        chat_msg = chat_msg.split('-->')[-1].strip()

    logger.info(
        f"[Knox] 수신 | msgType={msg_type} | sender={sender} | "
        f"knoxId={sender_knox} | chatroom={chatroom_id} | msg={chat_msg[:120]}"
    )

    # 첫 수신 시 chatroomId와 sender userID를 캐시에 저장
    if chatroom_id:
        from app.messenger.knox_messenger import _load_cached_chatroom_id, _save_chatroom_id
        if not _load_cached_chatroom_id():
            _save_chatroom_id(chatroom_id)
            logger.info(f"[Knox] 첫 메시지 수신 → chatroomId 자동 저장: {chatroom_id}")
    if sender:
        from pathlib import Path
        _sender_cache = Path(__file__).parent.parent / "data" / "knox_sender_user_id.txt"
        if not _sender_cache.exists():
            _sender_cache.parent.mkdir(parents=True, exist_ok=True)
            _sender_cache.write_text(sender, encoding="utf-8")
            logger.info(f"[Knox] sender userID 자동 저장: {sender} (senderKnoxId={sender_knox})")

    # ADAPTIVE_CARD: chatMsg JSON에서 sn 필드 추출
    if msg_type == "ADAPTIVE_CARD":
        try:
            card_data = _json.loads(chat_msg)
            chat_msg = (
                card_data.get("sn") or card_data.get("SN")
                or card_data.get("serialNumber") or ""
            ).strip().upper()
        except Exception:
            chat_msg = ""

    elif msg_type not in ("TEXT", ""):
        return JSONResponse(status_code=200, content={"status": "ignored"})

    if not chat_msg:
        asyncio.create_task(_knox_reply(chatroom_id, "SN을 입력해주세요."))
        return JSONResponse(status_code=200, content={"status": "ignored", "reason": "empty"})

    # Knox 시스템 메시지 (대화 시작, 홈버튼 등) → SN 입력 안내 전송
    _SYSTEM_KEYWORDS = {"intro", "welcome", "join", "leave", "invite"}
    _clean_msg = chat_msg.strip().strip("[]").lower()
    if _clean_msg in _SYSTEM_KEYWORDS:
        asyncio.create_task(_knox_reply(chatroom_id, "", with_card=True))
        return JSONResponse(status_code=200, content={"status": "intro"})

    # 키워드 처리: 카드 재전송
    _CARD_KEYWORDS = {"시작", "start", "도움말", "help", "카드", "card", "ㅎ", "hi", "안녕"}
    if chat_msg.strip().lower() in _CARD_KEYWORDS:
        asyncio.create_task(_knox_reply(chatroom_id, "통화품질 분석 카드를 전송합니다.", with_card=True))
        return JSONResponse(status_code=200, content={"status": "ignored", "reason": "empty"})

    # ── 여러 SN 지원: 쉼표/공백/줄바꿈으로 구분 ─────────────────────────────
    import re as _re
    # 그룹채팅 @멘션 제거 (예: @FA_대응_챗봇 SN번호 → SN번호)
    chat_msg = _re.sub(r'@\S+', '', chat_msg).strip()
    sn_list = [s.strip().upper() for s in _re.split(r'[,\s]+', chat_msg) if s.strip()]
    valid_sns   = [s for s in sn_list if re.match(r'^[A-Z0-9\-]{5,20}$', s)]
    invalid_sns = [s for s in sn_list if not re.match(r'^[A-Z0-9\-]{5,20}$', s)]

    if invalid_sns:
        asyncio.create_task(_knox_reply(
            chatroom_id,
            f"SN 형식 오류: {', '.join(invalid_sns)}\n영문+숫자+하이픈 5~20자로 입력해주세요.",
            with_card=not valid_sns,  # 유효한 SN이 없을 때만 카드 재전송
        ))

    if not valid_sns:
        return JSONResponse(status_code=200, content={"status": "ignored", "reason": "no valid SN"})

    # ── 각 SN별 Job 등록 및 파이프라인 실행 ──────────────────────────────────
    job_ids = []
    sns_str = ", ".join(valid_sns)
    asyncio.create_task(_knox_reply(
        chatroom_id,
        f"[{sns_str}] 조회중입니다. 잠시 후 결과를 전송합니다.",
        with_card=False,
    ))
    for sn_raw in valid_sns:
        job_id = str(uuid.uuid4())
        _chatbot_jobs[job_id] = {
            "job_id":     job_id,
            "sn":         sn_raw,
            "status":     "pending",
            "userId":     sender_knox or sender,
            "chatRoomId": chatroom_id,
            "created_at": time.time(),
            "source":     "knox",
        }
        logger.info(f"[Knox] 통화품질 분석 시작 | SN={sn_raw} | job_id={job_id}")
        asyncio.create_task(_run_knox_pipeline(job_id, sn_raw))
        job_ids.append(job_id)

    if len(valid_sns) > 1:
        asyncio.create_task(_knox_reply(
            chatroom_id,
            f"{len(valid_sns)}개 SN 분석을 시작합니다: {', '.join(valid_sns)}",
            with_card=False,
        ))

    return JSONResponse(status_code=200, content={"status": "accepted", "job_ids": job_ids, "sns": valid_sns})


@app.post("/message")
async def knox_message_receive(request: Request):
    """Knox Messenger 수신 엔드포인트 — 스테이지봇."""
    raw_body = await request.body()
    raw_text = raw_body.decode("utf-8", errors="replace")
    logger.info(f"[Knox /message STAGE] body={raw_text[:500]}")

    data = await _knox_parse_body(raw_text)
    if not data:
        return JSONResponse(status_code=200, content={"status": "ignored"})

    return await _knox_handle_message(data)


@app.post("/pro/message")
async def knox_prod_message_receive(request: Request):
    """Knox Messenger 수신 엔드포인트 — 운영봇."""
    raw_body = await request.body()
    raw_text = raw_body.decode("utf-8", errors="replace")
    logger.info(f"[Knox /pro/message PROD] body={raw_text[:500]}")

    data = await _knox_parse_body(raw_text)
    if not data:
        return JSONResponse(status_code=200, content={"status": "ignored"})

    return await _knox_handle_message(data)


@app.post("/api/knox/webhook")
async def knox_webhook(request: Request):
    """Knox 수신 웹훅 (구 URL — /message 로 포워딩)."""
    raw_body = await request.body()
    raw_text = raw_body.decode("utf-8", errors="replace")
    logger.info(f"[Knox /api/knox/webhook] body={raw_text[:500]}")

    data = await _knox_parse_body(raw_text)
    if not data:
        return JSONResponse(status_code=200, content={"status": "ignored"})

    return await _knox_handle_message(data)


@app.post("/messsage")
async def knox_message_typo(request: Request):
    """Knox 수신 URL 오타 대응 (/messsage → /message)."""
    raw_body = await request.body()
    raw_text = raw_body.decode("utf-8", errors="replace")
    logger.info(f"[Knox /messsage] body={raw_text[:500]}")

    data = await _knox_parse_body(raw_text)
    if not data:
        return JSONResponse(status_code=200, content={"status": "ignored"})
    return await _knox_handle_message(data)


async def _run_knox_pipeline(job_id: str, sn: str) -> None:
    """
    Knox Messenger 전용 파이프라인:
    통화품질 분석 실행 → PDF 생성 → Knox Messenger로 전송
    성공/실패 모두 SN 입력 카드를 재전송합니다.
    """
    job = _chatbot_jobs[job_id]
    chatroom_id = job.get("chatRoomId", "")

    PIPELINE_TIMEOUT = settings.QUERY_TIMEOUT_SECONDS + 300  # 쿼리 타임아웃 + 5분 여유

    async def _fail(reason: str) -> None:
        logger.error(f"[Knox Pipeline] 실패 | SN={sn} | reason={reason}")
        await _knox_reply(chatroom_id, f"[통화품질 분석 실패] SN: {sn}\n{reason}", with_card=True)

    try:
        # 타임아웃 적용하여 분석 실행
        await asyncio.wait_for(
            _run_chatbot_full_pipeline(job_id, sn),
            timeout=PIPELINE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        await _fail("내부 DB가 불안정합니다. 추후에 재시도 해주세요.")
        return
    except Exception as e:
        await _fail(f"분석 중 오류 발생: {type(e).__name__}")
        return

    if job.get("status") != "done":
        if job.get("error") == "db_unstable":
            await _fail("내부 DB가 불안정합니다. 추후에 재시도 해주세요.")
        else:
            await _fail(job.get("error") or "데이터 조회에 실패했습니다. SN을 확인해주세요.")
        return

    # 데이터 없음 → PDF/ZIP 생성 없이 Knox에 바로 알림
    if job.get("no_data"):
        await _knox_reply(chatroom_id, f"[SN: {sn}] 최근 {settings.QUERY_LOOKBACK_DAYS}일간 조회되는 데이터가 없습니다.", with_card=True)
        return

    if not settings.KNOX_MESSENGER_BASE_URL or not settings.KNOX_ACCESS_TOKEN:
        logger.warning(f"[Knox Pipeline] Knox 설정 미완료 (SN: {sn})")
        return

    import os as _os
    from app.analysis.pdf_generator import html_to_pdf
    from app.messenger.knox_messenger import KnoxMessengerClient, _load_cached_device_id

    html_path = _os.path.join(settings.CSV_DOWNLOAD_PATH, f"{sn}_analysis.html")
    pdf_path  = _os.path.join(settings.CSV_DOWNLOAD_PATH, f"{sn}_analysis.pdf")

    if not _os.path.exists(html_path):
        # HTML 미생성 → csv/log 파일로 재시도
        logger.warning(f"[Knox Pipeline] HTML 없음 → 재생성 시도 | {html_path}")
        from app.analysis.runner import generate_analysis_html as _gen_html
        _csv_path = _os.path.join(settings.CSV_DOWNLOAD_PATH, f"{sn}_inputdata.csv")
        _log_path = _os.path.join(settings.CSV_DOWNLOAD_PATH, f"{sn}_inputdata.LOG")
        _src = _log_path if _os.path.exists(_log_path) else (_csv_path if _os.path.exists(_csv_path) else None)
        if _src:
            _gen_html(sn, _src, settings.CSV_DOWNLOAD_PATH)
        if not _os.path.exists(html_path):
            await _fail("분석 HTML 파일을 찾을 수 없습니다.")
            return

    # HTML → PDF 변환
    try:
        pdf_ok = await asyncio.wait_for(html_to_pdf(html_path, pdf_path, neta_enabled=settings.NETA_ENABLED), timeout=600)
    except asyncio.TimeoutError:
        await _fail("PDF 변환 시간 초과.")
        return

    if not pdf_ok:
        # PDF 변환 실패가 실제 데이터 없음 때문인지 확인
        if not job.get("analysis_url"):
            days_val = settings.QUERY_LOOKBACK_DAYS
            await _knox_reply(chatroom_id, f"[SN: {sn}] 최근 {days_val}일간 조회되는 데이터가 없습니다.", with_card=True)
        else:
            await _fail("PDF 변환에 실패했습니다.")
        return

    # Knox Messenger 전송
    device_id = settings.KNOX_DEVICE_ID or _load_cached_device_id()
    client = KnoxMessengerClient(
        base_url=settings.KNOX_MESSENGER_BASE_URL,
        access_token=settings.KNOX_ACCESS_TOKEN,
        system_id=settings.KNOX_SYSTEM_ID,
        device_id=device_id,
        receiver_user_id=job.get("userId") or settings.KNOX_RECEIVER_USER_ID,
    )

    if not await client.ensure_device_id():
        await _fail("Knox Device ID 확보에 실패했습니다.")
        return

    chatroom_id = chatroom_id or await client.ensure_chatroom()
    if not chatroom_id:
        await _fail("Knox 대화방 확보에 실패했습니다.")
        return

    import time as _t
    feature_summary = job.get("feature_summary", "")

    # ── 1. PDF 업로드 & 전송 ───────────────────────────────────────────────────
    pdf_size_kb = _os.path.getsize(pdf_path) // 1024 if _os.path.exists(pdf_path) else 0
    logger.info(f"[Knox Pipeline] PDF 업로드 시도 | SN={sn} | 크기={pdf_size_kb}KB")
    pdf_upload = await client.upload_file(pdf_path)
    if pdf_upload:
        pdf_url, pdf_size = pdf_upload
        await client.send_file_message(
            chatroom_id=chatroom_id,
            download_url=pdf_url,
            filename=_os.path.basename(pdf_path),
            file_size=pdf_size,
        )
        logger.info(f"[Knox Pipeline] PDF 전송 완료 | SN={sn}")
    else:
        logger.warning(f"[Knox Pipeline] PDF 업로드 실패 | SN={sn} | 크기={pdf_size_kb}KB")
        await client.send_message(
            chatroom_id,
            f"[{sn}] PDF 업로드 실패 (파일 크기 {pdf_size_kb}KB — Knox 업로드 한도 초과 추정)"
        )

    logger.info(f"[Knox Pipeline] 전송 완료 | SN={sn}")
    await asyncio.sleep(2)

    # ── 2. SN 입력 카드 재전송 ────────────────────────────────────────────────
    await _knox_reply(chatroom_id, "", with_card=True)


# ─── 분석 파일 직접 서빙 ──────────────────────────────────────────────────────
@app.get("/files/{filename}")
async def serve_analysis_file(filename: str):
    """분석 결과 파일(PDF/HTML/ZIP)을 직접 내려줍니다."""
    import os as _os
    from fastapi.responses import FileResponse
    # path traversal 방지
    safe_name = _os.path.basename(filename)
    file_path = _os.path.join(settings.CSV_DOWNLOAD_PATH, safe_name)
    if not _os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    ext = safe_name.rsplit(".", 1)[-1].lower()
    mime = {
        "pdf": "application/pdf",
        "html": "text/html",
        "zip": "application/zip",
    }.get(ext, "application/octet-stream")
    return FileResponse(file_path, media_type=mime, filename=safe_name)


# ─── 대시보드 엔드포인트 ──────────────────────────────────────────────────────
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_ui():
    """분석 결과 대시보드 UI."""
    html_file = FRONTEND_DIR / "dashboard.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Dashboard</h1><p>frontend/dashboard.html을 확인하세요.</p>")


@app.get("/upload", response_class=HTMLResponse)
async def upload_page():
    """CSV/Excel 파일 업로드 → 분석 HTML + PDF 생성 페이지"""
    return HTMLResponse(content="""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>통화품질 분석 파일 업로드</title>
<style>
  body { font-family: sans-serif; max-width: 600px; margin: 60px auto; padding: 0 20px; background: #f5f5f5; }
  h1 { color: #1a237e; font-size: 1.4em; }
  .card { background: #fff; border-radius: 10px; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
  label { display: block; margin-bottom: 8px; font-weight: bold; color: #333; }
  input[type=file] { width: 100%; padding: 10px; border: 2px dashed #90caf9; border-radius: 6px; background: #e3f2fd; margin-bottom: 16px; box-sizing: border-box; }
  input[type=text] { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 6px; margin-bottom: 16px; box-sizing: border-box; font-size: 1em; }
  button { background: #1a237e; color: #fff; border: none; padding: 12px 30px; border-radius: 6px; font-size: 1em; cursor: pointer; width: 100%; }
  button:hover { background: #283593; }
  #status { margin-top: 16px; padding: 12px; border-radius: 6px; display: none; }
  .info { background: #e3f2fd; color: #0d47a1; }
  .success { background: #e8f5e9; color: #1b5e20; }
  .error { background: #ffebee; color: #b71c1c; }
  .hint { font-size: 0.85em; color: #888; margin-bottom: 20px; }
</style>
</head>
<body>
<h1>📄 통화품질 분석 파일 업로드</h1>
<div class="card">
  <p class="hint">CSV 또는 Excel 파일을 업로드하면 분석 HTML과 PDF를 생성합니다.</p>
  <form id="uploadForm">
    <label>파일 선택 (CSV / Excel)</label>
    <input type="file" id="fileInput" accept=".csv,.xlsx,.xls" required>
    <label>SN 번호 (파일명에서 자동 추출, 직접 입력 가능)</label>
    <input type="text" id="snInput" placeholder="예: R3CW804XAD">
    <button type="submit">업로드 & PDF 생성</button>
  </form>
  <div id="status"></div>
</div>
<script>
document.getElementById('fileInput').addEventListener('change', function() {
  const name = this.files[0]?.name || '';
  const sn = name.replace(/(_inputdata|_analysis)?(\\.csv|\\.xlsx|\\.xls)$/i, '');
  if (sn && !document.getElementById('snInput').value) {
    document.getElementById('snInput').value = sn;
  }
});

document.getElementById('uploadForm').addEventListener('submit', async function(e) {
  e.preventDefault();
  const file = document.getElementById('fileInput').files[0];
  const sn = document.getElementById('snInput').value.trim();
  if (!file) return;

  const status = document.getElementById('status');
  status.className = 'info';
  status.style.display = 'block';
  status.textContent = '⏳ 업로드 중... 분석 HTML 생성 후 PDF 변환 중입니다. 잠시 기다려주세요.';

  const form = new FormData();
  form.append('file', file);
  if (sn) form.append('sn', sn);

  try {
    const resp = await fetch('/api/upload-csv', { method: 'POST', body: form });
    if (resp.ok) {
      const blob = await resp.blob();
      const cd = resp.headers.get('Content-Disposition') || '';
      const fname = cd.match(/filename="?([^"]+)"?/)?.[1] || 'analysis.pdf';
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = fname; a.click();
      status.className = 'success';
      status.textContent = '✅ PDF 생성 완료! 다운로드가 시작됩니다.';
    } else {
      const err = await resp.json().catch(() => ({}));
      status.className = 'error';
      status.textContent = '❌ 오류: ' + (err.detail || resp.statusText);
    }
  } catch (e) {
    status.className = 'error';
    status.textContent = '❌ 요청 실패: ' + e.message;
  }
});
</script>
</body>
</html>""")


@app.post("/api/upload-csv")
async def upload_csv_and_generate_pdf(
    file: UploadFile = File(...),
    sn: str = Form(default=""),
):
    """
    CSV 또는 Excel 파일을 업로드받아 분석 HTML → PDF를 생성하고 반환합니다.
    """
    import os
    import tempfile
    from app.analysis.runner import generate_analysis_html
    from app.analysis.pdf_generator import html_to_pdf

    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in (".csv", ".xlsx", ".xls", ".log", ".txt"):
        raise HTTPException(status_code=400, detail="CSV, Excel, 또는 LOG 파일만 지원합니다.")

    # SN 결정 (Form 값 → 파일명에서 추출)
    if not sn:
        sn = os.path.splitext(filename)[0].replace("_inputdata", "").replace("_analysis", "").upper()

    contents = await file.read()

    with tempfile.TemporaryDirectory() as tmpdir:
        # 업로드 파일 저장
        raw_path = os.path.join(tmpdir, filename)
        with open(raw_path, "wb") as f:
            f.write(contents)

        # Excel이면 CSV로 변환
        if ext in (".xlsx", ".xls"):
            try:
                import openpyxl
                import csv
                wb = openpyxl.load_workbook(raw_path, read_only=True, data_only=True)
                ws = wb.active
                csv_path = os.path.join(tmpdir, f"{sn}_inputdata.csv")
                with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.writer(f)
                    for row in ws.iter_rows(values_only=True):
                        writer.writerow([("" if v is None else str(v)) for v in row])
                wb.close()
                input_filename = None  # CSV로 변환했으므로 기본 파일명 사용
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Excel 변환 실패: {e}")
        else:
            csv_path = raw_path
            input_filename = filename  # .csv / .log / .txt 원본 파일명 유지

        # HTML 생성
        html_path = generate_analysis_html(sn, csv_path, tmpdir, input_filename=input_filename)
        if not html_path:
            raise HTTPException(status_code=500, detail="분석 HTML 생성 실패")

        # PDF 변환
        pdf_path = os.path.join(tmpdir, f"{sn}_analysis.pdf")
        ok = await html_to_pdf(html_path, pdf_path, neta_enabled=settings.NETA_ENABLED)
        if not ok or not os.path.exists(pdf_path):
            raise HTTPException(status_code=500, detail="PDF 변환 실패")

        # PDF를 영구 저장 위치에 복사 후 반환
        import shutil
        final_pdf = os.path.join(settings.CSV_DOWNLOAD_PATH, f"{sn}_analysis.pdf")
        final_html = os.path.join(settings.CSV_DOWNLOAD_PATH, f"{sn}_analysis.html")
        try:
            os.makedirs(settings.CSV_DOWNLOAD_PATH, exist_ok=True)
            shutil.copy2(pdf_path, final_pdf)
            shutil.copy2(html_path, final_html)
        except Exception:
            pass

        pdf_bytes = open(pdf_path, "rb").read()

    from fastapi.responses import Response
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{sn}_analysis.pdf"'},
    )


@app.get("/analysis/{sn}", response_class=HTMLResponse)
async def serve_analysis_html(sn: str):
    """생성된 {sn}_analysis.html 파일을 브라우저에 직접 반환합니다."""
    import os
    sn = sn.upper().replace(".html", "")
    path = os.path.join(settings.CSV_DOWNLOAD_PATH, f"{sn}_analysis.html")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"분석 결과 HTML 없음: {sn}")
    return HTMLResponse(content=open(path, encoding="utf-8").read())


@app.get("/api/dashboard/results")
async def dashboard_results():
    """userdata 폴더의 모든 *_result.json 파일 목록을 반환합니다."""
    import os
    import json as _json
    save_dir = settings.CSV_DOWNLOAD_PATH
    results = []
    try:
        for fname in sorted(os.listdir(save_dir), reverse=True):
            if not fname.endswith("_result.json"):
                continue
            path = os.path.join(save_dir, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    data = _json.load(f)
                results.append({
                    "sn": data.get("sn", fname.replace("_result.json", "")),
                    "analyzed_at": data.get("analyzed_at", ""),
                    "feature_summary": data.get("feature_summary", ""),
                })
            except Exception:
                pass
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})
    return {"results": results}


@app.get("/api/dashboard/result/{sn}")
async def dashboard_result_detail(sn: str):
    """특정 SN의 결과 JSON을 반환합니다."""
    import os
    import json as _json
    sn = sn.upper()
    path = os.path.join(settings.CSV_DOWNLOAD_PATH, f"{sn}_result.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"{sn} 결과 파일이 없습니다.")
    try:
        with open(path, encoding="utf-8") as f:
            return _json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── WebSocket 엔드포인트 ─────────────────────────────────────────────────────
@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket 챗봇 엔드포인트.

    클라이언트 → 서버: {"sn": "ABC-123"}
    서버 → 클라이언트:
      {"type": "progress", "message": "..."} (진행 상태)
      {"type": "result",   "message": "...", "data": {...}} (최종 결과)
      {"type": "error",    "message": "..."} (오류)
    """
    await websocket.accept()
    logger.info(f"WebSocket 연결: {websocket.client}")

    # 동시 전송 시 메시지 순서 보장용 락
    ws_lock = asyncio.Lock()

    async def send_safe(msg_type: str, message: str, **extra):
        try:
            async with ws_lock:
                await websocket.send_json({"type": msg_type, "message": message, **extra})
        except Exception:
            pass

    try:
        while True:
            # 클라이언트 메시지 수신
            raw = await websocket.receive_json()
            sn_raw = raw.get("sn", "").strip().upper()

            # 입력 유효성 검사
            if not sn_raw:
                await send_safe("error", "SN을 입력해 주세요.")
                continue

            if not re.match(r'^[A-Z0-9\-]+$', sn_raw):
                await send_safe("error", "SN은 영문, 숫자, 하이픈(-)만 사용 가능합니다.")
                continue

            # 각 SN 쿼리를 독립 Task로 실행 → 동시에 여러 SN 처리 가능
            asyncio.create_task(_handle_query_safe(websocket, ws_lock, sn_raw))
            await asyncio.sleep(0)  # 이벤트 루프 제어권 즉시 양보 → Task 즉시 시작

    except WebSocketDisconnect:
        logger.info(f"WebSocket 연결 종료: {websocket.client}")
    except Exception as e:
        logger.error(f"WebSocket 오류: {e}")
        try:
            await _send(websocket, "error", "예기치 않은 오류가 발생했습니다.")
        except Exception:
            pass


async def _handle_query_safe(websocket: WebSocket, ws_lock: asyncio.Lock, sn: str):
    """ws_lock을 이용해 안전하게 전송하는 래퍼."""
    async def send_locked(msg_type: str, message: str, **extra):
        try:
            async with ws_lock:
                await websocket.send_json({"type": msg_type, "message": message, **extra})
        except Exception:
            pass

    await _handle_query(websocket, sn, send_fn=send_locked)


async def _handle_query(websocket: WebSocket, sn: str, send_fn=None):
    """단일 SN 조회 처리 (진행 상태 실시간 전송)"""
    if send_fn is None:
        async def send_fn(msg_type: str, message: str, **extra):
            await _send(websocket, msg_type, message)

    async def progress(msg: str):
        await send_fn("progress", msg)

    try:
        await progress(f"SN [{sn}] 조회 시작...")
        await progress(f"현재 대기 중인 브라우저 슬롯: {browser_pool.active_count}/{browser_pool.max_size}")

        # 1. 웹 스크래핑 SQL 쿼리 — LOG 파일 > CSV > live 쿼리 순서로 우선 처리
        import os as _os
        from app.scraper.query_runner import QueryResult as _QR
        _existing_log = _os.path.join(settings.CSV_DOWNLOAD_PATH, f"{sn}_inputdata.LOG")
        _existing_csv = _os.path.join(settings.CSV_DOWNLOAD_PATH, f"{sn}_inputdata.csv")
        if _os.path.exists(_existing_log):
            await progress(f"LOG 파일 재사용 (쿼리 생략): {_existing_log}")
            _log_rows = _parse_log_to_rows(_existing_log)
            query_result = _QR(sn=sn, success=True, csv_path=_existing_log, rows=_log_rows)
        elif _os.path.exists(_existing_csv) and _os.path.getsize(_existing_csv) > 0:
            await progress(f"기존 CSV 파일 재사용 (쿼리 생략): {_existing_csv}")
            query_result = _QR(sn=sn, success=True, csv_path=_existing_csv)
        else:
            query_result = await query_runner.run(sn, progress_callback=progress)

        if not query_result.success:
            await send_fn("error", query_result.error or "데이터 조회 실패",
                          session_expired=query_result.session_expired)
            return

        # 2. 데이터 가공
        await progress(f"CSV 데이터 가공 중... (파일: {query_result.csv_path})")
        processed = data_processor.process(query_result)

        if processed.error and not processed.summary_text:
            await send_fn("error", processed.error)
            return

        feature_summary = ", ".join(
            f"{f}:{len(t.rows)}건" for f, t in processed.feature_tables.items() if t.rows
        )
        await progress(f"데이터 가공 완료 — {feature_summary}")

        # 3. AI Agent 분석
        await progress(f"AI Agent 분석 요청 중... (최대 {settings.AI_AGENT_TIMEOUT}초 소요)")
        ai_response = await agent_client.analyze(processed)
        await progress("AI 분석 완료. 결과 전송 중...")

        # 4. 최종 결과 전송
        await send_fn("result", ai_response,
                      data={
                          "sn": sn,
                          "html_tables": processed.html_tables,
                          "summary": processed.summary_text,
                      })

    except asyncio.CancelledError:
        await send_fn("error", "요청이 취소되었습니다.")
    except Exception as e:
        logger.error(f"쿼리 처리 오류 [{sn}]: {e}")
        await send_fn("error", f"처리 중 오류가 발생했습니다: {str(e)}")


async def _send(websocket: WebSocket, msg_type: str, message: str):
    await websocket.send_json({"type": msg_type, "message": message})


# ─── 처리 결과 파일 저장 ──────────────────────────────────────────────────────
def _save_processing_files(sn: str, processed) -> None:
    """AI 입력 텍스트(.txt)와 처리 결과 테이블(.csv)을 저장합니다."""
    import csv
    import os

    save_dir = settings.CSV_DOWNLOAD_PATH
    try:
        os.makedirs(save_dir, exist_ok=True)
    except Exception as e:
        logger.warning(f"저장 폴더 생성 실패 [{save_dir}]: {e}")
        return

    # 1. AI 입력 텍스트 저장
    txt_path = os.path.join(save_dir, f"{sn}_ai_input.txt")
    try:
        with open(txt_path, "w", encoding="utf-8-sig") as f:
            f.write(processed.summary_text)
        logger.info(f"AI 입력 텍스트 저장 완료: {txt_path}")
    except Exception as e:
        logger.warning(f"AI 입력 텍스트 저장 실패: {e}")

    # 2. 처리 결과 Excel 저장 (feature별 시트)
    xlsx_path = os.path.join(save_dir, f"{sn}_processed.xlsx")
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill
        tables = processed.feature_tables
        if not tables:
            logger.warning("처리 결과 xlsx: feature_tables 비어있음 - 저장 스킵")
            return
        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # 기본 시트 제거
        for feat, table in tables.items():
            ws = wb.create_sheet(title=feat[:31])  # 시트명 최대 31자
            # 헤더 행
            ws.append(table.columns)
            for cell in ws[1]:
                cell.font = Font(bold=True)
                cell.fill = PatternFill("solid", fgColor="DCE6F1")
            # 데이터 행
            for row in table.rows:
                ws.append(row)
        wb.save(xlsx_path)
        logger.info(f"처리 결과 xlsx 저장 완료: {xlsx_path} ({len(tables)}개 feature)")
    except Exception as e:
        logger.warning(f"처리 결과 xlsx 저장 실패: {e}")


def _save_result_json(sn: str, ai_response: str, feature_summary: str,
                      station_entries: list, feature_tables: dict) -> None:
    """분석 완료 결과를 {SN}_result.json으로 저장합니다."""
    import os
    import json as _json
    from datetime import datetime

    save_dir = settings.CSV_DOWNLOAD_PATH
    path = os.path.join(save_dir, f"{sn}_result.json")
    try:
        os.makedirs(save_dir, exist_ok=True)
        tables_serializable = {}
        for feat, tbl in (feature_tables or {}).items():
            tables_serializable[feat] = {
                "columns": tbl.columns,
                "rows": tbl.rows,
                "footnotes": tbl.footnotes,
            }
        payload = {
            "sn": sn,
            "analyzed_at": datetime.now().isoformat(timespec="seconds"),
            "feature_summary": feature_summary,
            "ai_response": ai_response,
            "station_entries": station_entries or [],
            "feature_tables": tables_serializable,
        }
        with open(path, "w", encoding="utf-8") as f:
            _json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info(f"결과 JSON 저장 완료: {path}")
    except Exception as e:
        logger.warning(f"결과 JSON 저장 실패: {e}")


# ─── 기지국 정보 조회 헬퍼 ────────────────────────────────────────────────────
_PLMN_OPERATOR = {"45005": "skt", "45006": "lgu", "45008": "kt"}


async def _fetch_station_info(processed: ProcessedData) -> list[dict]:
    """MUTE 상위 3행 + DROP 첫 행의 TAC·PCI로 기지국 정보를 조회합니다.
    반환: [{"label": "MUTE 1위", "row": {...}}, ...]"""

    operator = _PLMN_OPERATOR.get(processed.plmn, "skt")
    if processed.plmn:
        logger.debug(f"사업자 판단: PLMN={processed.plmn} → {operator}")
    entries: list[dict] = []

    def _col_val(cols: list[str], row: list, col_name: str) -> str:
        return row[cols.index(col_name)] if col_name in cols else ""

    # ── MUTE 상위 3행 ────────────────────────────────────────────────────────
    mute = processed.feature_tables.get("MUTE")
    if mute and mute.rows:
        for i, row in enumerate(mute.rows[:3]):
            tac = _col_val(mute.columns, row, "TAC")
            pci = _col_val(mute.columns, row, "PCI")
            if tac and pci:
                try:
                    r = await station_scraper.search(operator, tac, pci)
                    if r.rows:
                        entries.append({"label": f"MUTE {i+1}위", "row": r.rows[0]})
                    else:
                        entries.append({"label": f"MUTE {i+1}위", "row": None, "tac": tac, "pci": pci})
                except Exception as e:
                    logger.warning(f"MUTE {i+1}위 기지국 조회 실패: {e}")
                    entries.append({"label": f"MUTE {i+1}위", "row": None, "tac": tac, "pci": pci})

    # ── DROP 첫 행 ───────────────────────────────────────────────────────────
    drop = processed.feature_tables.get("DROP")
    if drop and drop.rows:
        tac = _col_val(drop.columns, drop.rows[0], "TAC")
        pci = _col_val(drop.columns, drop.rows[0], "PCI")
        if tac and pci:
            try:
                r = await station_scraper.search(operator, tac, pci)
                if r.rows:
                    entries.append({"label": "DROP", "row": r.rows[0]})
                else:
                    entries.append({"label": "DROP", "row": None, "tac": tac, "pci": pci})
            except Exception as e:
                logger.warning(f"DROP 기지국 조회 실패: {e}")
                entries.append({"label": "DROP", "row": None, "tac": tac, "pci": pci})

    return entries


def _col_width(s: str) -> int:
    """한글 등 전각문자는 2, 나머지는 1로 계산한 표시 너비."""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in s)


def _col_pad(s: str, width: int) -> str:
    """표시 너비 기준으로 오른쪽 공백 패딩."""
    return s + " " * max(0, width - _col_width(s))


def _feature_tables_to_text(feature_tables: dict, feature_summary: str = "", query_days: int | None = None) -> str:
    """Feature 분포 + 각 feature 테이블(상위 3행, MUTE_EXTRA 전체)을 마크다운 표로 변환합니다."""
    _FEAT_ORDER = ["MUTE", "MUTE_EXTRA", "DROP", "DROP_RAW", "RLFI", "SCGF", "NSVC", "ATTF", "CRSH"]
    parts = []

    if feature_summary:
        parts.append(f"**[ 주요 Feature 분포 ]**\n\n{feature_summary}")

    for feat in _FEAT_ORDER:
        table = feature_tables.get(feat)
        if not table or not table.rows:
            continue
        col_map = _FEATURE_DISPLAY_COLS.get(feat, [])
        valid = [(disp, actual) for disp, actual in col_map if actual in table.columns]
        if not valid:
            continue
        label = _FEATURE_LABELS.get(feat, feat)
        total = len(table.rows)
        lines = [f"**◆ {label} ({total}건)**"]

        if feat == "MUTE_EXTRA":
            # 전체 값 표시 (마크다운 표)
            row = table.rows[0]
            headers = [disp for disp, _ in valid]
            values = [str(row[table.columns.index(actual)]) for disp, actual in valid]
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "|".join("---" for _ in headers) + "|")
            lines.append("| " + " | ".join(values) + " |")
        else:
            # NSVC: 전체 rows 표시 / 나머지: 상위 3행
            row_limit = len(table.rows) if feat in ("NSVC", "DROP_RAW") else 3
            # zero_hide_cols: 표시 행에서 전부 0인 컬럼 제외
            if hasattr(table, "zero_hide_cols") and table.zero_hide_cols:
                shown = table.rows[:row_limit]
                valid = [
                    (disp, actual) for disp, actual in valid
                    if actual not in table.zero_hide_cols
                    or any(str(r[table.columns.index(actual)]).strip() not in ("0", "") for r in shown)
                ]
            display_rows = [
                [_trunc(str(row[table.columns.index(actual)]), 15) for _, actual in valid]
                for row in table.rows[:row_limit]
            ]
            headers = [disp for disp, _ in valid]
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "|".join("---" for _ in headers) + "|")
            for row_vals in display_rows:
                lines.append("| " + " | ".join(row_vals) + " |")

        table_text = "\n".join(lines)

        # 괄호 안 설명을 표 바깥(아래)에 빈 줄로 분리하여 표시
        if table.footnotes:
            footnote_lines = "\n".join(f"※ {fn}" for fn in table.footnotes)
            table_text = table_text + "\n\n" + footnote_lines

        parts.append(table_text)

    # 표시할 테이블이 하나도 없으면 조회 없음 메시지
    has_tables = len(parts) > (1 if feature_summary else 0)
    if not has_tables:
        no_data_msg = f"최근 {query_days or settings.QUERY_LOOKBACK_DAYS}일간 조회되는 데이터가 없습니다."
        parts.append(no_data_msg)

    return "\n\n".join(parts)


def _feature_table_to_vertical_text(feat: str, table) -> str:
    """단일 feature 테이블을 세로 형식(행=인자, 열=순위1·2·3)으로 변환합니다."""
    col_map = _FEATURE_DISPLAY_COLS.get(feat, [])
    valid = [(disp, actual) for disp, actual in col_map if actual in table.columns]
    if not valid or not table.rows:
        return ""

    label = _FEATURE_LABELS.get(feat, feat)
    n_total = len(table.rows)

    if feat == "MUTE_EXTRA":
        row = table.rows[0]
        lines = [f"◆ {label}"]
        for disp, actual in valid:
            lines.append(f"{disp}: {row[table.columns.index(actual)]}")
        return "\n".join(lines)

    # 최대 3개 행(순위)을 열로, 인자를 행으로 전치
    display_rows = table.rows[:3]
    n_cols = len(display_rows)

    # 셀 값 미리 계산
    cells = {}
    for pi, (disp, actual) in enumerate(valid):
        idx = table.columns.index(actual)
        for ci, row in enumerate(display_rows):
            cells[(pi, ci)] = _trunc(str(row[idx]), 10)

    # 컬럼 너비: 인자명 열 / 순위 열
    param_w = max(_col_width("인자"), max(_col_width(disp) for disp, _ in valid))
    col_ws = [
        max(_col_width(str(ci + 1)), max(_col_width(cells[(pi, ci)]) for pi in range(len(valid))))
        for ci in range(n_cols)
    ]

    lines = [f"◆ {label} ({n_total}건)"]
    lines.append(
        _col_pad("인자", param_w) + " | " +
        " | ".join(_col_pad(str(ci + 1), col_ws[ci]) for ci in range(n_cols))
    )
    lines.append("-" * param_w + "-+-" + "-+-".join("-" * w for w in col_ws))
    for pi, (disp, _) in enumerate(valid):
        lines.append(
            _col_pad(disp, param_w) + " | " +
            " | ".join(_col_pad(cells[(pi, ci)], col_ws[ci]) for ci in range(n_cols))
        )
    return "\n".join(lines)


def _station_entries_to_text(entries: list[dict]) -> str:
    """기지국 entries를 push용 텍스트로 변환합니다."""
    KEY_W = 10

    def _kv(key: str, val) -> str:
        return _col_pad(key + " :", KEY_W + 2) + str(val)

    parts = []
    for e in entries:
        r = e.get("row")
        label = e["label"]
        lines = [f"◆ {label} 기지국"]
        if not r:
            lines.append(f"조회 결과 없음 (TAC:{e.get('tac','-')} PCI:{e.get('pci','-')})")
        else:
            operator = r.get('operator', '-')
            week = r.get('week') or r.get('period') or r.get('date_range') or ''
            operator_str = f"{operator} | {week}" if week else operator

            lines.append(_kv("지역",     r.get('region', '-')))
            lines.append(_kv("사업자",   operator_str))
            lines.append(_kv("TAC/PCI",  f"{r.get('tac','-')} / {r.get('pci','-')}  DLCh:{r.get('dlch','-')}"))
            lines.append(_kv("Vendor",   r.get('vendor', '-')))
            lines.append(_kv("단말/호",  f"{r.get('device_cnt','-')} / {r.get('call_cnt','-')}"))
            lines.append(_kv("Drop/RLF", f"{r.get('drop_cnt','-')} / {r.get('rlf_cnt','-')}"))
            lines.append(_kv("HO실패",   r.get('ho_failure_cnt', '-')))
            anomaly_raw = r.get('anomaly_score', '-')
            try:
                anomaly_warn = float(str(anomaly_raw)) >= 100
            except (ValueError, TypeError):
                anomaly_warn = False
            anomaly_display = f"🔵 {anomaly_raw}" + (" ⚠ 주의필요" if anomaly_warn else "")
            lines.append(_kv("이상점수", anomaly_display))
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


# (표시명, 실제 컬럼명) - 표시명은 챗봇에 보여줄 짧은 이름
_FEATURE_DISPLAY_COLS = {
    "MUTE": [
        ("ACT", "ACT"), ("TAC", "TAC"), ("PCI", "PCI"), ("Band", "Band"),
        ("UBMT", "UBMT"), ("RSMT", "RSMT"), ("RNMT", "RNMT"), ("DBMT", "DBMT"),
        ("ECNT", "ECNT"), ("RSRP", "RSRP"), ("SINR", "SINR"), ("BLER", "BLER"),
    ],
    "MUTE_EXTRA": [
        ("SAMS", "SAMS"), ("SMBU", "SMBU"), ("MCST", "MCST"),
    ],
    "DROP": [
        ("ACT", "ACT"), ("TAC", "TAC"), ("PCI", "PCI"), ("DLCh", "DLCh"),
        ("발생횟수", "발생횟수"), ("RxP0", "RxP0"), ("RxP1", "RxP1"),
        ("BLER", "BLER"), ("SIP값", "SIPR"),
    ],
    "DROP_RAW": [
        ("날짜", "날짜"), ("TAC", "TAC"), ("PCI", "PCI"),
    ],
    "RLFI": [
        ("ACT", "ACT"), ("TAC", "TAC"), ("PID", "PID"), ("DCh", "DCh"),
        ("발생횟수", "발생횟수"), ("RxP", "RxP"), ("원인", "원인"),
    ],
    "SCGF": [
        ("TAC", "TAC"), ("PhID", "PhID"), ("L밴드", "L밴드"), ("N밴드", "N밴드"),
        ("발생횟수", "발생횟수"), ("원인", "원인"),
    ],
    "NSVC": [
        ("날짜", "Date"), ("합계", "합계"),
        ("LEV0", "LEV0"), ("LEV1", "LEV1"), ("LEV2", "LEV2"),
        ("LEV3", "LEV3"), ("LEV4", "LEV4"), ("LEV5", "LEV5"),
    ],
    "ATTF": [
        ("PLMN", "PLMN"), ("ACT", "ACT_"), ("TAC", "TAC_"), ("PCI", "PhID_"), ("DLCh", "DLCh"),
        ("Count", "Count"), ("원인", "EMMC_Counts"),
    ],
    "CRSH": [
        ("ACT", "ACT_"), ("TAC", "TAC_"), ("PCI", "PhID"),
        ("Count", "Count"), ("원인", "InCa_Counts"),
    ],
}

# 표시 레이블 (feature key → 챗봇 표시용 이름)
_FEATURE_LABELS = {
    "MUTE":       "MUTE",
    "MUTE_EXTRA": "MUTE 추가정보 (SAMS/SMBU/MCST 발생횟수)",
    "DROP":       "DROP",
    "DROP_RAW":   "Drop 발생현황",
    "RLFI":       "RLFI",
    "SCGF":       "SCGF",
    "NSVC":       "NSVC",
    "ATTF":       "ATTF (접속실패)",
    "CRSH":       "CRSH (크래시)",
}


def _trunc(s: str, n: int = 12) -> str:
    """긴 문자열을 n자로 잘라 '…' 붙입니다."""
    return s if len(s) <= n else s[:n - 1] + "…"


_WIDE_COLS = {"원인"}  # 원인 계열 컬럼은 width:2 로 넓게 표시


def _col_width_card(disp: str) -> int:
    """Adaptive Card ColumnSet width 값 반환 (원인 컬럼은 2, 나머지 1)."""
    return 2 if disp in _WIDE_COLS else 1


def _build_feature_table_blocks(feature_tables: dict) -> list[dict]:
    """MUTE·MUTE_EXTRA·DROP·RLFI·SCGF 집계 테이블을 Adaptive Card 블록으로 변환합니다."""
    blocks = []
    for feat in ["MUTE", "MUTE_EXTRA", "DROP", "RLFI", "SCGF"]:
        table = feature_tables.get(feat)
        if not table or not table.rows:
            continue

        col_map = _FEATURE_DISPLAY_COLS.get(feat, [])
        valid = [(disp, actual) for disp, actual in col_map if actual in table.columns]
        if not valid:
            continue

        label = _FEATURE_LABELS.get(feat, feat)
        blocks.append({
            "type": "TextBlock",
            "text": f"◆ {label} ({len(table.rows)}건)",
            "weight": "Bolder",
            "spacing": "Medium",
        })

        if feat == "MUTE_EXTRA":
            # SAMS/SMBU/MCST: FactSet으로 표시
            row = table.rows[0]
            facts = [
                {"title": disp, "value": str(row[table.columns.index(actual)]) or "-"}
                for disp, actual in valid
            ]
            blocks.append({"type": "FactSet", "facts": facts, "spacing": "Small"})
        else:
            # 헤더 행 (ColumnSet)
            blocks.append({
                "type": "ColumnSet",
                "style": "emphasis",
                "spacing": "Small",
                "columns": [
                    {
                        "type": "Column", "width": _col_width_card(disp),
                        "items": [{"type": "TextBlock", "text": disp,
                                   "weight": "Bolder", "size": "Small",
                                   "wrap": False, "color": "Accent"}],
                    }
                    for disp, _ in valid
                ],
            })
            # 데이터 행 (ColumnSet per row)
            for row in table.rows:
                blocks.append({
                    "type": "ColumnSet",
                    "spacing": "None",
                    "columns": [
                        {
                            "type": "Column", "width": _col_width_card(disp),
                            "items": [{"type": "TextBlock",
                                       "text": _trunc(str(row[table.columns.index(actual)]), 10),
                                       "size": "Small", "wrap": disp in _WIDE_COLS}],
                        }
                        for disp, actual in valid
                    ],
                })

    return blocks


def _build_station_card_blocks(entries: list[dict]) -> list[dict]:
    """기지국 entries를 Adaptive Card FactSet 블록으로 변환합니다."""
    blocks = []
    for e in entries:
        r = e.get("row")
        label = e["label"]
        blocks.append({
            "type": "TextBlock",
            "text": f"◆ {label} 기지국",
            "weight": "Bolder",
            "spacing": "Medium",
        })
        if not r:
            blocks.append({
                "type": "TextBlock",
                "text": f"조회 결과 없음 (TAC:{e.get('tac','-')} PCI:{e.get('pci','-')})",
                "wrap": True,
                "isSubtle": True,
            })
            continue
        blocks.append({
            "type": "FactSet",
            "spacing": "Small",
            "facts": [
                {"title": "지역",    "value": str(r.get("region", "-"))},
                {"title": "사업자",  "value": f"{r.get('operator','-')} | {r.get('year','-')}년 {r.get('week','-')}주차"},
                {"title": "TAC/PCI", "value": f"{r.get('tac','-')} / {r.get('pci','-')}  DLCh:{r.get('dlch','-')}"},
                {"title": "Vendor",  "value": str(r.get("vendor", "-"))},
                {"title": "단말/호", "value": f"{r.get('device_cnt','-')} / {r.get('call_cnt','-')}"},
                {"title": "Drop/RLF","value": f"{r.get('drop_cnt','-')} / {r.get('rlf_cnt','-')}"},
                {"title": "HO실패",  "value": str(r.get("ho_failure_cnt", "-"))},
                {"title": "이상점수","value": str(r.get("anomaly_score", "-"))},
            ],
        })
    return blocks


# ─── 챗봇 전용 백그라운드 파이프라인 ─────────────────────────────────────────
async def _run_chatbot_full_pipeline(job_id: str, sn: str, query_days: int | None = None) -> None:
    """챗봇 Job: SQL 조회 → 데이터 가공 → AI 분석 전체 파이프라인 실행"""
    job = _chatbot_jobs[job_id]
    job["status"] = "running"
    days = query_days if query_days is not None else settings.QUERY_LOOKBACK_DAYS

    try:
        if settings.MOCK_MODE:
            # ── MOCK 모드: 실제 Superset 조회 없이 더미 데이터 사용 ──────────────
            logger.info(f"[Chatbot Job {job_id}] MOCK 모드 실행 - SN: {sn}")
            await asyncio.sleep(3)  # 조회 시뮬레이션
            job["status"] = "done"
            job["ai_response"] = (
                f"[MOCK] SN [{sn}] 분석 결과\n\n"
                "■ 주요 지역 분석\n"
                "- PLMN 45008 / LTE / TAC 12345 지역에서 ECNT 150건 (전체의 60%)\n"
                "- 해당 지역 평균 RSRP: -105 dBm (약한 신호)\n\n"
                "■ 종합 의견\n"
                "단말기 SN 조회 결과 특정 지역 기지국에서 집중적인 무음 이벤트가 발생하고 있습니다. "
                "해당 셀의 기지국 파라미터 점검이 필요합니다.\n\n"
                "(이 결과는 MOCK 테스트 데이터입니다)"
            )
            job["feature_summary"] = "MUTE: 250건 (Mock)"
            await _push_card_to_chatroom(job)
            return

        # 1. SQL 쿼리 실행 — LOG 파일 > 캐시 > live 쿼리 순서로 우선 처리
        import os as _os
        from app.scraper.query_runner import QueryResult
        _log_path = _os.path.join(settings.CSV_DOWNLOAD_PATH, f"{sn}_inputdata.LOG")
        if _os.path.exists(_log_path):
            logger.info(f"[Chatbot Job {job_id}] LOG 파일 존재 → 쿼리 생략: {_log_path}")
            _log_rows = _parse_log_to_rows(_log_path)
            query_result = QueryResult(sn=sn, success=True, csv_path=_log_path, rows=_log_rows)
        else:
            from app.prefetch.cache_manager import get_cached_csv_path, is_cached
            cached_path = get_cached_csv_path(sn)
            if cached_path:
                import os as _os2
                # 빈 CSV(no data) = 캐시 만료 무관하게 재쿼리 스킵
                if _os2.path.getsize(cached_path) == 0:
                    logger.info(f"[Chatbot Job {job_id}] no data 캐시 → 쿼리 스킵: {cached_path}")
                    query_result = QueryResult(sn=sn, success=True, csv_path=cached_path)
                elif is_cached(sn):
                    logger.info(f"[Chatbot Job {job_id}] 캐시 히트 → {cached_path} (쿼리 생략)")
                    query_result = QueryResult(sn=sn, success=True, csv_path=cached_path)
                else:
                    logger.info(f"[Chatbot Job {job_id}] 캐시 만료 → live 쿼리 실행")
                    query_result = await query_runner.run(sn, days=days)
            else:
                query_result = await query_runner.run(sn, days=days)

        if not query_result.success:
            job["status"] = "error"
            err_msg = query_result.error or ""
            _db_unstable_kw = ["timeout", "timed out", "TimeoutError", "connection", "network", "ERR_", "불안정"]
            if query_result.session_expired:
                job["error"] = "세션이 만료되었습니다. 관리자에게 재로그인을 요청해 주세요."
            elif any(kw.lower() in err_msg.lower() for kw in _db_unstable_kw):
                job["error"] = "db_unstable"
            else:
                job["error"] = err_msg or "데이터 조회 실패"
            await _push_card_to_chatroom(job)
            return

        # 데이터 없음 처리 (쿼리 성공했으나 결과 없음 — 빈 CSV 포함)
        import os as _os
        no_data = (
            query_result.csv_path is None
            or not _os.path.exists(query_result.csv_path)
            or _os.path.getsize(query_result.csv_path) == 0
        )
        # 헤더만 있고 실제 데이터 행이 없는 CSV도 no_data로 처리
        if not no_data:
            try:
                with open(query_result.csv_path, encoding="utf-8-sig", errors="ignore") as _csv_f:
                    _data_rows = sum(1 for ln in _csv_f if ln.strip()) - 1  # 헤더 제외
                if _data_rows <= 0:
                    no_data = True
            except Exception:
                pass
        if no_data:
            job["status"] = "done"
            job["no_data"] = True
            job["ai_response"] = f"최근 {days}일간 조회되는 데이터가 없습니다."
            job["feature_summary"] = ""
            await _push_card_to_chatroom(job)
            return

        # 2. 데이터 가공
        processed = data_processor.process(query_result)

        if processed.error and not processed.summary_text:
            job["status"] = "error"
            job["error"] = processed.error
            await _push_card_to_chatroom(job)
            return

        # 2-1. AI 입력 텍스트 및 처리 결과 CSV 저장
        _save_processing_files(sn, processed)

        # 2-2. log_analyzer HTML 생성
        _analysis_html_path = generate_analysis_html(
            sn, query_result.csv_path, settings.CSV_DOWNLOAD_PATH
        )
        if not _analysis_html_path:
            logger.error(f"[Chatbot Job {job_id}] HTML 생성 실패 | csv={query_result.csv_path}")
        job["analysis_url"] = (
            f"{settings.BASE_URL}/analysis/{sn}" if _analysis_html_path else None
        )

        # 2-3. Knox Teams 채널 파일 전송 (설정된 경우)
        if _analysis_html_path and settings.TEAMS_FILE_API_URL:
            from app.messenger.teams_sender import send_html_to_teams
            await send_html_to_teams(
                _analysis_html_path, sn,
                settings.TEAMS_FILE_API_URL,
                settings.TEAMS_API_KEY,
                settings.TEAMS_CHANNEL_ID,
            )

        # 2-4. Knox Messenger 전송 (HTML zip 우선, 실패 시 PDF)
        # Knox 파이프라인(source=knox)은 _run_knox_pipeline이 직접 전송하므로 여기서 스킵
        if settings.KNOX_MESSENGER_ENABLED and settings.KNOX_MESSENGER_BASE_URL and job.get("source") != "knox":
            from app.analysis.pdf_generator import html_to_pdf
            from app.messenger.knox_messenger import send_pdf_via_knox
            import os as _os2
            _send_path = None
            if _analysis_html_path:
                _pdf_path = _os2.path.join(settings.CSV_DOWNLOAD_PATH, f"{sn}_analysis.pdf")
                if await html_to_pdf(_analysis_html_path, _pdf_path, neta_enabled=settings.NETA_ENABLED):
                    _send_path = _pdf_path
                else:
                    logger.warning(f"[Chatbot Job {job_id}] PDF 생성 실패 - Knox 전송 스킵")
            if _send_path:
                await send_pdf_via_knox(
                    pdf_path=_send_path,
                    sn=sn,
                    base_url=settings.KNOX_MESSENGER_BASE_URL,
                    access_token=settings.KNOX_ACCESS_TOKEN,
                    system_id=settings.KNOX_SYSTEM_ID,
                    device_id=settings.KNOX_DEVICE_ID,
                    receiver_user_id=settings.KNOX_RECEIVER_USER_ID,
                )

        # 3. AI 분석 (사용자 데이터만 전송)
        if settings.AI_AGENT_ENABLED:
            ai_response = await agent_client.analyze(processed)
        else:
            ai_response = ""
            logger.info(f"[Chatbot Job {job_id}] AI Agent 비활성화 - 스킵")

        # 4. 기지국 정보 조회 (별도 - AI에 보내지 않고 챗봇에만 표시)
        if settings.STATION_SCRAPER_ENABLED:
            station_entries = await _fetch_station_info(processed)
            if station_entries:
                logger.info(f"[Chatbot Job {job_id}] 기지국 정보 조회 완료 ({len(station_entries)}건)")
        else:
            station_entries = []
            logger.info(f"[Chatbot Job {job_id}] 기지국 조회 비활성화 - 스킵")

        feature_summary = " > ".join(
            f"{f}({len(t.rows)}건)"
            for f, t in sorted(processed.feature_tables.items(), key=lambda x: len(x[1].rows), reverse=True)[:9]
            if t.rows
        )

        job["status"] = "done"
        job["ai_response"] = ai_response
        job["feature_summary"] = feature_summary
        job["station_entries"] = station_entries  # 기지국 구조화 데이터
        job["station_text"] = _station_entries_to_text(station_entries)  # push용 텍스트
        job["feature_tables"] = processed.feature_tables  # MUTE/DROP 표 데이터
        job["device_model"] = processed.device_model
        job["plmn"] = processed.plmn

        # 5. 결과 JSON 저장 (대시보드용)
        _save_result_json(sn, ai_response, feature_summary, station_entries, processed.feature_tables)

        # 6. 결과 카드 자동 push (CHATBOT_PUSH_URL 설정 시)
        await _push_card_to_chatroom(job)

    except Exception as e:
        logger.error(f"[Chatbot Job {job_id}] 처리 오류: {e}")
        job["status"] = "error"
        job["error"] = str(e)
        await _push_card_to_chatroom(job)


# ─── Webhook 엔드포인트 (챗봇 Builder Adaptive Card) ──────────────────────────

# 챗봇 Job TTL: 2시간 후 자동 삭제
_JOB_TTL_SECONDS = 7200


class WebhookRequest(BaseModel):
    """챗봇 Builder에서 Adaptive Card Action.Submit 시 전달되는 데이터"""
    action: Optional[str] = None
    sn_value: Optional[str] = None
    job_id: Optional[str] = None
    userId: Optional[str] = None
    chatRoomId: Optional[str] = None

    model_config = {"extra": "allow"}  # 알 수 없는 필드 허용 (챗봇 Builder 버전 대응)


def _cleanup_expired_jobs() -> None:
    """TTL이 지난 챗봇 Job을 메모리에서 삭제합니다."""
    now = time.time()
    expired = [jid for jid, j in _chatbot_jobs.items() if now - j.get("created_at", now) > _JOB_TTL_SECONDS]
    for jid in expired:
        del _chatbot_jobs[jid]
    if expired:
        logger.info(f"[Webhook] 만료된 Job {len(expired)}개 정리 완료")


def _parse_webhook_body(raw_body: bytes, content_type: str) -> dict:
    """
    챗봇 Builder가 보내는 다양한 body 형식을 파싱합니다.
    항상 dict를 반환합니다 (파싱 실패 시 빈 dict).

    지원 형식:
      - application/json  : JSON 객체 또는 JSON 문자열(이중 인코딩)
      - application/x-www-form-urlencoded : form 데이터
      - 기타 : JSON 파싱 시도
    """
    import json as _json
    import urllib.parse as _urlparse

    text = raw_body.decode("utf-8", errors="replace").strip()

    def _to_dict(obj) -> dict | None:
        """파싱 결과가 dict인 경우만 반환, 아니면 None"""
        return obj if isinstance(obj, dict) else None

    # 1. JSON 객체 직접 파싱
    if text.startswith("{"):
        try:
            result = _json.loads(text)
            d = _to_dict(result)
            if d is not None:
                return d
        except Exception:
            pass

    # 2. JSON 문자열 이중 인코딩 (body 자체가 "\"{ ... }\"" 형태)
    if text.startswith('"'):
        try:
            inner = _json.loads(text)   # 외부 문자열 벗기기
            if isinstance(inner, str):
                result = _json.loads(inner)
                d = _to_dict(result)
                if d is not None:
                    return d
        except Exception:
            pass

    # 3. form-urlencoded 형식
    if "application/x-www-form-urlencoded" in content_type:
        try:
            return dict(_urlparse.parse_qsl(text))
        except Exception:
            pass

    # 4. 최후 시도: JSON 파싱 (dict인 경우만)
    try:
        result = _json.loads(text)
        d = _to_dict(result)
        if d is not None:
            return d
    except Exception:
        pass

    return {}


@app.post("/webhook")
async def webhook_handler(request: Request):
    """
    챗봇 Builder Adaptive Card 제출 수신 엔드포인트.

    [SN 조회 요청] Action.Submit → {"action": "search_sn", "sn_value": "SN-12345", "userId": "...", "chatRoomId": "..."}
      → 백그라운드 Job 시작 후 즉시 접수 카드 반환 (60초 timeout 대응)

    [결과 확인 요청] Action.Submit → {"action": "check_result", "job_id": "...", "userId": "..."}
      → Job 상태에 따라 결과 카드 또는 처리 중 카드 반환
    """
    try:
        raw_body = await request.body()
        content_type = request.headers.get("content-type", "")
        raw_text = raw_body.decode("utf-8", errors="replace")

        # ── raw body 무조건 로깅 (Samsung 챗봇 Builder 형식 파악용) ──────────────
        logger.info(
            f"[Webhook] RAW 수신 | len={len(raw_body)} | content-type={content_type} "
            f"| body={raw_text[:800]}"
        )

        # ── JSON 파싱 (Samsung 챗봇 이중 인코딩 + trailing comma 대응) ──────────
        import json as _json
        import re as _re

        def _fix_json(s: str) -> str:
            """trailing comma 제거 (Samsung 챗봇 Builder 비표준 JSON 대응)"""
            return _re.sub(r',\s*([}\]])', r'\1', s)

        data: dict = {}
        if raw_body:
            try:
                # 1차 파싱 시도 (trailing comma 제거 후)
                parsed = _json.loads(_fix_json(raw_text))

                if isinstance(parsed, dict):
                    # 정상: JSON 객체
                    data = parsed
                elif isinstance(parsed, str):
                    # 이중 인코딩: 파싱 결과가 문자열 → 다시 파싱
                    inner = _json.loads(_fix_json(parsed))
                    if isinstance(inner, dict):
                        data = inner
                    else:
                        logger.warning(f"[Webhook] 2차 파싱도 dict 아님: {type(inner).__name__}")

            except Exception as e:
                logger.warning(f"[Webhook] JSON 파싱 실패 ({e}), form 시도")
                import urllib.parse as _up
                try:
                    data = dict(_up.parse_qsl(raw_text))
                except Exception:
                    pass

        logger.info(
            f"[Webhook] 파싱 결과 | keys={list(data.keys())} "
            f"| action={data.get('action')} | sn_value={data.get('sn_value')} "
            f"| userId={data.get('userId')} | chatRoomId={data.get('chatRoomId')}"
        )

        if not data:
            logger.error(f"[Webhook] 파싱 실패 - body가 비어있거나 알 수 없는 형식 | raw={raw_text[:300]}")
            return _webhook_error_card("요청 데이터를 파싱할 수 없습니다. 관리자에게 로그를 확인해 달라고 요청하세요.")

        _cleanup_expired_jobs()

        action = (data.get("action") or "").strip()
        user_id = (data.get("userId") or "").strip()
        # chatRoomId: 챗봇 Builder 템플릿 변수 미치환 케이스 방어
        chat_room_id_raw = str(data.get("chatRoomId") or "")
        chat_room_id = chat_room_id_raw if not chat_room_id_raw.startswith("${") else ""

        # ── 결과 확인 요청 ──────────────────────────────────────────────────────
        if action == "check_result":
            job_id = (data.get("job_id") or "").strip()
            job = _chatbot_jobs.get(job_id)

            if not job:
                return _webhook_error_card("조회 결과를 찾을 수 없습니다. SN을 다시 입력해 주세요.")

            # 본인 job인지 확인 (userId가 있는 경우에만 검증)
            if user_id and job.get("userId") and job["userId"] != user_id:
                return _webhook_error_card("접근 권한이 없습니다.")

            sn = job.get("sn", "")
            status = job.get("status", "unknown")

            if status == "done":
                return JSONResponse(_build_result_card(sn, job.get("ai_response", ""), job.get("feature_summary", ""), job.get("station_entries"), job.get("station_text", ""), job.get("feature_tables"), job.get("analysis_url", "")))
            elif status == "error":
                return _webhook_error_card(job.get("error", "처리 중 오류가 발생했습니다."))
            else:
                return JSONResponse(_build_status_card(sn, job_id))

        # ── SN 조회 요청 ─────────────────────────────────────────────────────────
        # body → 헤더 순으로 sn_value 탐색 (chatbot Builder 헤더 전달 방식 대응)
        sn_raw = (
            data.get("sn_value")
            or request.headers.get("sn_value")
            or request.headers.get("Sn_value")
            or request.headers.get("SN_VALUE")
            or ""
        ).strip().upper()

        if not sn_raw:
            logger.info("[Webhook] sn_value 없음 → SN 입력 폼 카드 반환 (앱카드 초기 로딩)")
            return JSONResponse(_build_input_form_card())

        # 쉼표/공백/줄바꿈으로 구분된 다중 SN 파싱 (최대 5개)
        sn_list = [s.strip() for s in re.split(r'[,\s\n]+', sn_raw) if s.strip()]
        sn_list = sn_list[:5]

        # SN 형식 검증
        for sn in sn_list:
            if len(sn) > 50:
                return _webhook_error_card(f"SN이 너무 깁니다 (최대 50자): {sn}")
            if not re.match(r'^[A-Z0-9\-]+$', sn):
                return _webhook_error_card(f"SN 형식이 올바르지 않습니다: {sn}")

        logger.info(f"[Webhook] SN 조회 시작: {sn_list} | userId={user_id} | chatRoomId={chat_room_id}")

        # SN별 Job 생성 + 병렬 파이프라인 시작
        # 조회 기간 (days): 웹훅 payload 우선, 없으면 config 기본값
        days_raw = data.get("days") or data.get("day") or data.get("lookback_days")
        try:
            query_days = int(days_raw) if days_raw is not None else settings.QUERY_LOOKBACK_DAYS
            query_days = max(1, min(query_days, 30))  # 1~30일 범위 제한
        except (ValueError, TypeError):
            query_days = settings.QUERY_LOOKBACK_DAYS

        for sn in sn_list:
            job_id = str(uuid.uuid4())
            _chatbot_jobs[job_id] = {
                "status": "pending",
                "sn": sn,
                "userId": user_id or None,
                "chatRoomId": chat_room_id or None,
                "created_at": time.time(),
                "query_days": query_days,
            }
            asyncio.create_task(_run_chatbot_full_pipeline(job_id, sn, query_days))

        sn_display = ", ".join(sn_list)
        return JSONResponse({
            "title": f"SN {len(sn_list)}개 조회 중",
            "text": (
                f"아래 SN 조회를 시작했습니다:\n{sn_display}\n\n"
                "분석에 최대 60분이 소요될 수 있습니다.\n"
                "완료되면 각각 결과를 전송해 드립니다. 잠시만 기다려 주세요."
            )
        })

    except Exception as exc:
        logger.error(
            f"[Webhook] 처리 중 예외 발생: {type(exc).__name__}: {exc}",
            exc_info=True,
        )
        # 500 대신 Adaptive Card 오류 메시지 반환 (챗봇 Builder가 카드를 기대함)
        return _webhook_error_card(f"서버 내부 오류가 발생했습니다. 관리자에게 문의하세요. ({type(exc).__name__})")


# ─── Adaptive Card 빌더 ───────────────────────────────────────────────────────

def _build_input_form_card() -> dict:
    """SN 입력 폼 카드 — Input.Text + Action.Submit(intent:appCard) → API 호출"""
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.3",
        "body": [
            {
                "type": "TextBlock",
                "text": "통화품질 분석서비스 SN 조회",
                "size": "Medium",
                "weight": "Bolder",
            },
            {
                "type": "TextBlock",
                "text": "조회할 단말기의 SN을 입력하고 조회 버튼을 눌러 주세요.",
                "wrap": True,
                "isSubtle": True,
                "spacing": "Small",
            },
            {
                "type": "Input.Text",
                "id": "sn_value",
                "placeholder": "SN 입력 (예: R5KL10BNKT)",
                "label": "단말기 SN",
                "isRequired": True,
                "errorMessage": "SN을 입력해 주세요.",
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "조회",
                "data": {
                    "intent": "appCard",
                    "entity": {
                        "name": "SN조회",
                        "update": "True",
                    },
                },
            }
        ],
    }


def _build_processing_card(sn: str, job_id: str) -> dict:
    """SN 조회 접수 카드 — 즉시 반환, 결과 확인 버튼 포함"""
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.3",
        "body": [
            {
                "type": "TextBlock",
                "text": "SN 조회 접수",
                "size": "Medium",
                "weight": "Bolder",
            },
            {
                "type": "ColumnSet",
                "style": "emphasis",
                "columns": [
                    {
                        "type": "Column",
                        "width": "100px",
                        "items": [{"type": "TextBlock", "text": "SN", "weight": "Bolder", "wrap": True}],
                    },
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [{"type": "TextBlock", "text": sn, "wrap": True}],
                    },
                ],
            },
            {
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column",
                        "width": "100px",
                        "items": [{"type": "TextBlock", "text": "상태", "wrap": True}],
                    },
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [{"type": "TextBlock", "text": "조회 중", "color": "Warning", "wrap": True}],
                    },
                ],
            },
            {
                "type": "TextBlock",
                "text": "조회가 시작되었습니다. 약 5~15분 소요됩니다.\n완료 후 아래 버튼으로 결과를 확인하세요.",
                "wrap": True,
                "isSubtle": True,
                "spacing": "Medium",
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "결과 확인",
                "data": {"action": "check_result", "job_id": job_id},
            }
        ],
    }


def _build_status_card(sn: str, job_id: str) -> dict:
    """아직 처리 중일 때 반환하는 카드"""
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.3",
        "body": [
            {
                "type": "TextBlock",
                "text": "SN 조회 진행 중",
                "size": "Medium",
                "weight": "Bolder",
            },
            {
                "type": "ColumnSet",
                "style": "emphasis",
                "columns": [
                    {
                        "type": "Column",
                        "width": "100px",
                        "items": [{"type": "TextBlock", "text": "SN", "weight": "Bolder", "wrap": True}],
                    },
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [{"type": "TextBlock", "text": sn, "wrap": True}],
                    },
                ],
            },
            {
                "type": "TextBlock",
                "text": "아직 처리 중입니다. 잠시 후 다시 확인해 주세요.",
                "wrap": True,
                "color": "Attention",
                "spacing": "Medium",
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "다시 확인",
                "data": {"action": "check_result", "job_id": job_id},
            }
        ],
    }


def _build_result_card(sn: str, ai_response: str, feature_summary: str, station_entries: list | None = None, station_text: str = "", feature_tables: dict | None = None, analysis_url: str = "") -> dict:
    """분석 완료 결과 카드"""
    MAX_AI_LEN = 800
    ai_text = ai_response if len(ai_response) <= MAX_AI_LEN else ai_response[:MAX_AI_LEN] + "..."

    body = [
        {
            "type": "TextBlock",
            "text": f"SN 조회 결과: {sn}",
            "size": "Medium",
            "weight": "Bolder",
        },
        {
            "type": "ColumnSet",
            "style": "emphasis",
            "columns": [
                {
                    "type": "Column",
                    "width": "100px",
                    "items": [{"type": "TextBlock", "text": "SN", "weight": "Bolder", "wrap": True}],
                },
                {
                    "type": "Column",
                    "width": "stretch",
                    "items": [{"type": "TextBlock", "text": sn, "wrap": True}],
                },
            ],
        },
        {
            "type": "ColumnSet",
            "columns": [
                {
                    "type": "Column",
                    "width": "100px",
                    "items": [{"type": "TextBlock", "text": "분석 데이터", "wrap": True}],
                },
                {
                    "type": "Column",
                    "width": "stretch",
                    "items": [{"type": "TextBlock", "text": feature_summary, "wrap": True}],
                },
            ],
        },
        {
            "type": "TextBlock",
            "text": "■ AI 분석 결과",
            "weight": "Bolder",
            "spacing": "Large",
        },
        {
            "type": "TextBlock",
            "text": ai_text,
            "wrap": True,
            "spacing": "Small",
        },
    ]

    # 기지국 정보 섹션 추가 (FactSet 형식)
    if station_entries:
        body.append({
            "type": "TextBlock",
            "text": "■ 기지국 정보",
            "weight": "Bolder",
            "spacing": "Large",
        })
        body.extend(_build_station_card_blocks(station_entries))

    actions = []
    if analysis_url:
        actions.append({
            "type": "Action.OpenUrl",
            "title": "상세 분석 보기",
            "url": analysis_url,
        })

    card: dict = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.3",
        "body": body,
    }
    if actions:
        card["actions"] = actions
    return card


def _webhook_error_card(message: str) -> JSONResponse:
    """오류 메시지를 Adaptive Card 형식으로 반환합니다."""
    return JSONResponse(
        status_code=200,  # 챗봇 Builder는 200 응답을 기대합니다
        content={
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.3",
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"오류: {message}",
                    "color": "Attention",
                    "wrap": True,
                }
            ],
        },
    )
