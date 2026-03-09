"""
AI Agent Client - 가공된 데이터를 내부 AI Agent로 전송하고 응답을 수신

내부 AI Agent가 REST API를 제공한다고 가정합니다.
Agent가 다른 프로토콜(gRPC, WebSocket 등)을 사용한다면 이 파일을 수정하세요.
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
        가공된 단말기 데이터를 AI Agent에 전송하고 분석 결과를 반환합니다.

        Args:
            processed: DataProcessor가 생성한 ProcessedData

        Returns:
            AI Agent의 분석 텍스트
        """
        if processed.error and not processed.summary_text:
            return f"데이터 조회 중 오류가 발생했습니다: {processed.error}"

        if not processed.ai_prompt:
            return processed.summary_text or "조회된 데이터가 없습니다."

        payload = {
            "sn": processed.sn,
            "prompt": processed.ai_prompt,
            "context": {
                "device_model": processed.device.model,
                "status": processed.device.status,
                "customer_name": processed.device.customer_name,
                "contract_active": processed.device.contract_active,
                "service_history_count": len(processed.device.service_history),
            },
        }

        try:
            logger.info(f"AI Agent 요청 전송 - SN: {processed.sn}")
            response = await self._client.post(
                settings.AI_AGENT_URL,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            # Agent 응답 형식에 따라 키 이름을 조정하세요
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
        """AI Agent 연결 실패 시 DB 조회 결과만으로 응답합니다."""
        return (
            f"[AI 분석 서비스 연결 실패]\n\n"
            f"아래는 데이터베이스 조회 결과입니다:\n\n"
            f"{processed.summary_text}"
        )

    async def close(self):
        await self._client.aclose()


# 싱글턴 인스턴스
agent_client = AgentClient()
