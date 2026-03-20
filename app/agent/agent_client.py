"""
AI Agent Client - 삼성 내부 AI Agent API 연동

API 스펙:
  POST https://agent.sec.samsung.net/api/v1/run/{flow_id}?stream=false
  Headers: x-api-key, Content-Type: application/json
  Body:
    {
      "input_type": "chat",
      "output_type": "chat",
      "input_value": "MUTE",
      "component_inputs": {
        "TextInput-n8kcD": { "input_value": "<실제 데이터>" },
        "prompt-rFpiB":    { "template":    "<분석 지시사항>" }
      }
    }
  Response:
    { "outputs": [ { "outputs": [ { "results": { "message": { "text": "..." } } } ] } ] }
"""

import asyncio
import logging
import warnings

import requests
import urllib3

# 사내 SSL 인증서로 인한 InsecureRequestWarning 억제
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

from app.config import settings
from app.processor.data_processor import ProcessedData

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_DELAYS = [2, 4, 8]  # 지수 백오프 (초)



def _post_to_agent(payload: dict) -> dict:
    """동기 requests로 AI Agent에 POST 요청합니다. (Windows 시스템 프록시 자동 사용)"""
    response = requests.post(
        settings.AI_AGENT_URL,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": settings.AI_AGENT_API_KEY,
        },
        verify=False,       # 사내 SSL 인증서 검증 비활성화
        timeout=(10, settings.AI_AGENT_TIMEOUT),  # (connect, read)
    )
    response.raise_for_status()
    return response.json()


class AgentClient:
    """삼성 내부 AI Agent와 통신하는 클라이언트입니다."""

    async def analyze(self, processed: ProcessedData) -> str:
        """
        AI Agent에 프롬프트를 전송하고 분석 결과를 반환합니다.
        """
        if processed.error and not processed.summary_text:
            return f"데이터 조회 중 오류가 발생했습니다: {processed.error}"

        if not processed.summary_text:
            return "조회된 데이터가 없습니다."

        payload = {
            "input_type": "chat",
            "output_type": "chat",
            "input_value": "MUTE",
            "component_inputs": {
                settings.AI_AGENT_INPUT_KEY: {
                    "input_value": processed.summary_text,   # 실제 데이터
                },
            },
        }

        # AI Agent 입력값을 파일로 저장 (확인용)
        self._save_input_log(processed.sn, processed.summary_text)

        for attempt in range(_MAX_RETRIES):
            try:
                logger.info(f"AI Agent 요청 전송 - SN: {processed.sn} (시도 {attempt + 1}/{_MAX_RETRIES})")
                # asyncio.to_thread로 동기 requests 호출 (Windows 시스템 프록시 자동 적용)
                data = await asyncio.to_thread(_post_to_agent, payload)

                result = self._extract_text(data)
                if not result:
                    logger.warning(f"AI Agent 응답에서 텍스트 추출 실패: {data}")
                    return self._fallback_response(processed)

                logger.info(f"AI Agent 응답 수신 완료 - SN: {processed.sn}")
                return result

            except requests.exceptions.Timeout:
                logger.warning(f"AI Agent 타임아웃 ({settings.AI_AGENT_TIMEOUT}초) - SN: {processed.sn}, 시도 {attempt + 1}")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"AI Agent 연결 실패 - SN: {processed.sn}, 시도 {attempt + 1}: {e}")
            except requests.exceptions.HTTPError as e:
                logger.error(
                    f"AI Agent HTTP 오류: {e.response.status_code}\n"
                    f"URL: {settings.AI_AGENT_URL}\n"
                    f"응답 body: {e.response.text[:500]}"
                )
                return self._fallback_response(processed)  # HTTP 오류는 재시도 없이 반환
            except Exception as e:
                logger.error(f"AI Agent 통신 오류 [{type(e).__name__}]: {e}", exc_info=True)
                return self._fallback_response(processed)

            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_DELAYS[attempt]
                logger.info(f"AI Agent 재시도 대기 {delay}초...")
                await asyncio.sleep(delay)

        logger.error(f"AI Agent 최대 재시도 횟수({_MAX_RETRIES}) 초과 - SN: {processed.sn}")
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
            logger.info(f"AI 입력값 저장 완료: {path}")
        except Exception as e:
            logger.error(f"AI 입력값 저장 실패 [{type(e).__name__}]: {e}\n저장 경로: {path}", exc_info=True)

    async def close(self):
        pass


# 싱글턴 인스턴스
agent_client = AgentClient()
