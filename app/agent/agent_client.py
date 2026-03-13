"""
AI Agent Client - 삼성 내부 AI Agent API 연동

API 스펙:
  POST https://agent.sec.samsung.net/api/v1/run/{flow_id}?stream=false
  Headers: x-api-key, Content-Type: application/json
  Body:
    {
      "input_type": "chat",
      "output_type": "chat",
      "component_inputs": {
        "<input_key>": { "input_value": "<text>" }
      }
    }
  Response:
    { "outputs": [ { "outputs": [ { "results": { "message": { "text": "..." } } } ] } ] }
"""

import logging

import httpx

from app.config import settings
from app.processor.data_processor import ProcessedData

logger = logging.getLogger(__name__)


class AgentClient:
    """삼성 내부 AI Agent와 통신하는 클라이언트입니다."""

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.AI_AGENT_TIMEOUT),
            headers={
                "Content-Type": "application/json",
                "x-api-key": settings.AI_AGENT_API_KEY,
            },
        )

    async def analyze(self, processed: ProcessedData) -> str:
        """
        AI Agent에 프롬프트를 전송하고 분석 결과를 반환합니다.
        """
        if processed.error and not processed.summary_text:
            return f"데이터 조회 중 오류가 발생했습니다: {processed.error}"

        if not processed.ai_prompt:
            return processed.summary_text or "조회된 데이터가 없습니다."

        payload = {
            "input_type": "chat",
            "output_type": "chat",
            "component_inputs": {
                settings.AI_AGENT_INPUT_KEY: {
                    "input_value": processed.ai_prompt,
                }
            },
        }

        # AI Agent 입력값을 파일로 저장 (확인용)
        self._save_input_log(processed.sn, processed.ai_prompt)

        try:
            logger.info(f"AI Agent 요청 전송 - SN: {processed.sn}")
            response = await self._client.post(settings.AI_AGENT_URL, json=payload)
            response.raise_for_status()
            data = response.json()

            result = self._extract_text(data)
            if not result:
                logger.warning(f"AI Agent 응답에서 텍스트 추출 실패: {data}")
                return self._fallback_response(processed)

            logger.info(f"AI Agent 응답 수신 완료 - SN: {processed.sn}")
            return result

        except httpx.TimeoutException:
            logger.error(f"AI Agent 타임아웃 ({settings.AI_AGENT_TIMEOUT}초) - SN: {processed.sn}")
            return self._fallback_response(processed)
        except httpx.HTTPStatusError as e:
            logger.error(
                f"AI Agent HTTP 오류: {e.response.status_code}\n"
                f"URL: {settings.AI_AGENT_URL}\n"
                f"응답 body: {e.response.text[:500]}"
            )
            return self._fallback_response(processed)
        except httpx.ConnectError as e:
            logger.error(f"AI Agent 연결 실패 (네트워크/방화벽 확인 필요): {e}")
            return self._fallback_response(processed)
        except Exception as e:
            logger.error(f"AI Agent 통신 오류 [{type(e).__name__}]: {e}", exc_info=True)
            return self._fallback_response(processed)

    @staticmethod
    def _extract_text(data: dict) -> str:
        """API 응답에서 텍스트를 추출합니다."""
        # 형식: {"outputs": [{"outputs": [{"results": {"message": {"text": "..."}}}]}]}
        try:
            return data["outputs"][0]["outputs"][0]["results"]["message"]["text"]
        except (KeyError, IndexError, TypeError):
            pass

        # 단순 flat 형식 fallback
        return (
            data.get("result")
            or data.get("answer")
            or data.get("text")
            or data.get("output")
            or ""
        )

    @staticmethod
    def _fallback_response(processed: ProcessedData) -> str:
        return (
            "[AI 분석 서비스 연결 실패]\n\n"
            "아래는 수집된 네트워크 이벤트 데이터 요약입니다:\n\n"
            f"{processed.summary_text}"
        )

    @staticmethod
    def _save_input_log(sn: str, prompt: str) -> None:
        """AI Agent에 전송하는 입력값을 텍스트 파일로 저장합니다."""
        import os
        save_dir = settings.CSV_DOWNLOAD_PATH
        path = os.path.join(save_dir, f"{sn}_ai_input.txt")
        try:
            os.makedirs(save_dir, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(prompt)
            logger.info(f"AI 입력값 저장: {path}")
        except Exception as e:
            logger.warning(f"AI 입력값 저장 실패: {e}")

    async def close(self):
        await self._client.aclose()


# 싱글턴 인스턴스
agent_client = AgentClient()
