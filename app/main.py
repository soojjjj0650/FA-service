"""
FA Chatbot Service - FastAPI 메인 애플리케이션

엔드포인트:
  GET  /                          → 챗봇 UI (HTML)
  GET  /batch                     → 배치 쿼리 UI (HTML, 최대 5개 SN 동시 실행)
  POST /api/query                 → SN 조회 (REST, 동기 응답)
  POST /api/batch-query           → 최대 5개 SN 동시 쿼리 + CSV 다운로드 (비동기 Job)
  GET  /api/batch-status/{job_id} → 배치 Job 진행 상태 폴링
  WS   /ws/chat                   → SN 조회 (WebSocket, 실시간 진행 상태)
  GET  /api/status                → 브라우저 풀 상태 확인
  POST /api/session/reset         → 세션 수동 초기화
  POST /webhook                   → 챗봇 Builder Adaptive Card 제출 수신 (SN 조회)
"""

import asyncio
import logging
import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from app.config import settings
from app.scraper.browser_pool import browser_pool
from app.scraper.query_runner import query_runner
from app.scraper.session_manager import session_manager
from app.processor.data_processor import data_processor
from app.agent.agent_client import agent_client

# ─── 로깅 설정 ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─── FastAPI 앱 ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="FA Chatbot Service",
    description="단말기 SN 기반 FA 지원 챗봇",
    version="1.0.0",
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

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
    logger.info("FA Chatbot Service 시작")


@app.on_event("shutdown")
async def shutdown():
    await browser_pool.shutdown()
    await agent_client.close()
    logger.info("FA Chatbot Service 종료")


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
    return HTMLResponse(content="<h1>FA Chatbot</h1><p>frontend/index.html을 확인하세요.</p>")


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
    쿼리 실행 시간이 길기 때문에 WebSocket(/ws/chat)을 권장합니다.
    """
    try:
        # 1. 웹 스크래핑으로 SQL 쿼리 실행
        query_result = await query_runner.run(request.sn)

        # 2. 데이터 가공
        processed = data_processor.process(query_result)

        # 3. AI Agent 분석
        ai_response = await agent_client.analyze(processed)

        return JSONResponse({
            "sn": request.sn,
            "success": query_result.success,
            "session_expired": query_result.session_expired,
            "result": ai_response,
            "device": {
                "model": processed.device.model,
                "status": processed.device.status,
                "customer_name": processed.device.customer_name,
                "contract_active": processed.device.contract_active,
            } if query_result.success else None,
            "error": query_result.error,
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"쿼리 처리 오류 - SN: {request.sn}: {e}")
        raise HTTPException(status_code=500, detail="서버 오류가 발생했습니다.")


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

        # 1. 웹 스크래핑 SQL 쿼리 (5~15분 소요)
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
            f"{f}:{len(t.rows)}건" for f, t in processed.feature_tables.items()
        ) or "데이터 없음"
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


# ─── 챗봇 전용 백그라운드 파이프라인 ─────────────────────────────────────────
async def _run_chatbot_full_pipeline(job_id: str, sn: str) -> None:
    """챗봇 Job: SQL 조회 → 데이터 가공 → AI 분석 전체 파이프라인 실행"""
    job = _chatbot_jobs[job_id]
    job["status"] = "running"

    try:
        # 1. SQL 쿼리 실행
        query_result = await query_runner.run(sn)

        if not query_result.success:
            job["status"] = "error"
            job["error"] = (
                "세션이 만료되었습니다. 관리자에게 재로그인을 요청해 주세요."
                if query_result.session_expired
                else (query_result.error or "데이터 조회 실패")
            )
            return

        # 2. 데이터 가공
        processed = data_processor.process(query_result)

        if processed.error and not processed.summary_text:
            job["status"] = "error"
            job["error"] = processed.error
            return

        # 3. AI 분석
        ai_response = await agent_client.analyze(processed)

        feature_summary = "  |  ".join(
            f"{f}: {len(t.rows)}건" for f, t in processed.feature_tables.items()
        ) or "데이터 없음"

        job["status"] = "done"
        job["ai_response"] = ai_response
        job["feature_summary"] = feature_summary

    except Exception as e:
        logger.error(f"[Chatbot Job {job_id}] 처리 오류: {e}")
        job["status"] = "error"
        job["error"] = str(e)


# ─── Webhook 엔드포인트 (챗봇 Builder Adaptive Card) ──────────────────────────
class WebhookRequest(BaseModel):
    """챗봇 Builder에서 Adaptive Card Action.Submit 시 전달되는 데이터"""
    action: Optional[str] = None
    sn_value: Optional[str] = None
    job_id: Optional[str] = None


@app.post("/webhook")
async def webhook_handler(request: WebhookRequest):
    """
    챗봇 Builder Adaptive Card 제출 수신 엔드포인트.

    [SN 조회 요청] Action.Submit → {"action": "search_sn", "sn_value": "SN-12345"}
      → 백그라운드 Job 시작 후 즉시 접수 카드 반환 (60초 timeout 대응)

    [결과 확인 요청] Action.Submit → {"action": "check_result", "job_id": "..."}
      → Job 상태에 따라 결과 카드 또는 처리 중 카드 반환
    """

    # ── 결과 확인 요청 ─────────────────────────────────────────────────────────
    if request.action == "check_result":
        job_id = (request.job_id or "").strip()
        job = _chatbot_jobs.get(job_id)

        if not job:
            return _webhook_error_card("조회 결과를 찾을 수 없습니다. SN을 다시 입력해 주세요.")

        sn = job.get("sn", "")
        status = job.get("status", "unknown")

        if status == "done":
            return JSONResponse(_build_result_card(sn, job["ai_response"], job["feature_summary"]))
        elif status == "error":
            return _webhook_error_card(job.get("error", "처리 중 오류가 발생했습니다."))
        else:
            return JSONResponse(_build_status_card(sn, job_id))

    # ── SN 조회 요청 ───────────────────────────────────────────────────────────
    sn_raw = (request.sn_value or "").strip().upper()

    if not sn_raw:
        return _webhook_error_card("SN을 입력해 주세요.")
    if len(sn_raw) > 50:
        return _webhook_error_card("SN이 너무 깁니다 (최대 50자).")
    if not re.match(r'^[A-Z0-9\-]+$', sn_raw):
        return _webhook_error_card("SN은 영문, 숫자, 하이픈(-)만 사용 가능합니다.")

    logger.info(f"[Webhook] SN 조회 요청: {sn_raw}")

    job_id = str(uuid.uuid4())
    _chatbot_jobs[job_id] = {"status": "pending", "sn": sn_raw}
    asyncio.create_task(_run_chatbot_full_pipeline(job_id, sn_raw))

    return JSONResponse(_build_processing_card(sn_raw, job_id))


# ─── Adaptive Card 빌더 ───────────────────────────────────────────────────────

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


def _build_result_card(sn: str, ai_response: str, feature_summary: str) -> dict:
    """분석 완료 결과 카드"""
    MAX_AI_LEN = 800
    ai_text = ai_response if len(ai_response) <= MAX_AI_LEN else ai_response[:MAX_AI_LEN] + "..."

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.3",
        "body": [
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
        ],
    }


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
