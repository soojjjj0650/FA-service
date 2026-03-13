"""
AI Agent Client - 텍스트 프롬프트를 내부 AI Agent로 전송하고 응답 수신

내부 AI Agent는 text 형식만 수신 가능.
요청: POST {AI_AGENT_URL}  body: {"text": "<prompt>"}
응답: {"result": "<분석 텍스트>"}  (또는 "answer" / "text" 키)
"""

import logging

import httpx

from app.config import settings
from app.processor.data_processor import ProcessedData

logger = logging.getLogger(__name__)


class AgentClient:
    """내부 AI Agent와 통신하는 클라이언트입니다."""

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.AI_AGENT_TIMEOUT),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.AI_AGENT_API_KEY}",
            },
        )

    async def analyze(self, processed: ProcessedData) -> str:
        """
        AI Agent에 텍스트 프롬프트를 전송하고 분석 결과를 반환합니다.

        Returns:
            AI Agent 분석 텍스트
        """
        if processed.error and not processed.summary_text:
            return f"데이터 조회 중 오류가 발생했습니다: {processed.error}"

        if not processed.ai_prompt:
            return processed.summary_text or "조회된 데이터가 없습니다."

        # 내부 AI Agent는 text 형식만 수신
        payload = {"text": processed.ai_prompt}

        try:
            logger.info(f"AI Agent 요청 전송 - SN: {processed.sn}")
            response = await self._client.post(settings.AI_AGENT_URL, json=payload)
            response.raise_for_status()
            data = response.json()

            result = data.get("result") or data.get("answer") or data.get("text") or ""
            if not result:
                logger.warning(f"AI Agent 응답이 비어 있습니다: {data}")
                return self._fallback_response(processed)

            logger.info(f"AI Agent 응답 수신 완료 - SN: {processed.sn}")
            return result

        except httpx.TimeoutException:
            logger.error(f"AI Agent 타임아웃 - SN: {processed.sn}")
            return self._fallback_response(processed)
        except httpx.HTTPStatusError as e:
            logger.error(f"AI Agent HTTP 오류: {e.response.status_code} - {e.response.text}")
            return self._fallback_response(processed)
        except Exception as e:
            logger.error(f"AI Agent 통신 오류: {e}")
            return self._fallback_response(processed)

    @staticmethod
    def _fallback_response(processed: ProcessedData) -> str:
        """AI Agent 연결 실패 시 수집 데이터 요약만 반환합니다."""
        return (
            f"[AI 분석 서비스 연결 실패]\n\n"
            f"아래는 수집된 네트워크 이벤트 데이터 요약입니다:\n\n"
            f"{processed.summary_text}"
        )

    async def close(self):
        await self._client.aclose()


# 싱글턴 인스턴스
agent_client = AgentClient()
