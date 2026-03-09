"""
FA Chatbot Service - FastAPI 메인 애플리케이션

엔드포인트:
  GET  /                    → 챗봇 UI (HTML)
  POST /api/query           → SN 조회 (REST, 동기 응답)
  WS   /ws/chat             → SN 조회 (WebSocket, 실시간 진행 상태)
  GET  /api/status          → 브라우저 풀 상태 확인
  POST /api/session/reset   → 세션 수동 초기화
"""

import asyncio
import logging
import re
from pathlib import Path

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
        # 영문, 숫자, 하이픈만 허용
        if not re.match(r'^[A-Z0-9\-]+$', v):
            raise ValueError("SN은 영문, 숫자, 하이픈(-)만 사용 가능합니다.")
        return v


# ─── REST 엔드포인트 ──────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    """챗봇 UI를 반환합니다."""
    html_file = FRONTEND_DIR / "index.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>FA Chatbot</h1><p>frontend/index.html을 확인하세요.</p>")


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

    try:
        while True:
            # 클라이언트 메시지 수신
            raw = await websocket.receive_json()
            sn_raw = raw.get("sn", "").strip().upper()

            # 입력 유효성 검사
            if not sn_raw:
                await _send(websocket, "error", "SN을 입력해 주세요.")
                continue

            if not re.match(r'^[A-Z0-9\-]+$', sn_raw):
                await _send(websocket, "error", "SN은 영문, 숫자, 하이픈(-)만 사용 가능합니다.")
                continue

            await _handle_query(websocket, sn_raw)

    except WebSocketDisconnect:
        logger.info(f"WebSocket 연결 종료: {websocket.client}")
    except Exception as e:
        logger.error(f"WebSocket 오류: {e}")
        try:
            await _send(websocket, "error", "예기치 않은 오류가 발생했습니다.")
        except Exception:
            pass


async def _handle_query(websocket: WebSocket, sn: str):
    """단일 SN 조회 처리 (진행 상태 실시간 전송)"""

    async def progress(msg: str):
        await _send(websocket, "progress", msg)

    try:
        await progress(f"SN [{sn}] 조회 시작...")
        await progress(f"현재 대기 중인 브라우저 슬롯: {browser_pool.active_count}/{browser_pool.max_size}")

        # 1. 웹 스크래핑 SQL 쿼리 (5~15분 소요)
        query_result = await query_runner.run(sn, progress_callback=progress)

        if not query_result.success:
            await websocket.send_json({
                "type": "error",
                "message": query_result.error or "데이터 조회 실패",
                "session_expired": query_result.session_expired,
            })
            return

        # 2. 데이터 가공
        await progress("데이터 가공 중...")
        processed = data_processor.process(query_result)

        if processed.error and not processed.summary_text:
            await _send(websocket, "error", processed.error)
            return

        # 3. AI Agent 분석
        await progress("AI 분석 중...")
        ai_response = await agent_client.analyze(processed)

        # 4. 최종 결과 전송
        await websocket.send_json({
            "type": "result",
            "message": ai_response,
            "data": {
                "sn": sn,
                "model": processed.device.model,
                "status": processed.device.status,
                "customer_name": processed.device.customer_name,
                "contract_active": processed.device.contract_active,
                "service_history_count": len(processed.device.service_history),
                "summary": processed.summary_text,
            },
        })

    except asyncio.CancelledError:
        await _send(websocket, "error", "요청이 취소되었습니다.")
    except Exception as e:
        logger.error(f"쿼리 처리 오류 [{sn}]: {e}")
        await _send(websocket, "error", f"처리 중 오류가 발생했습니다: {str(e)}")


async def _send(websocket: WebSocket, msg_type: str, message: str):
    await websocket.send_json({"type": msg_type, "message": message})
