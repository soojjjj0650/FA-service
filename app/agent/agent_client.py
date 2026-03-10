"""
Claude API Client - 가공된 단말기 데이터를 Anthropic Claude API로 분석

Anthropic Python SDK를 사용하며, 스트리밍 + adaptive thinking으로
응답 품질과 타임아웃 안정성을 확보합니다.
"""

import logging

import anthropic

from app.config import settings
from app.processor.data_processor import ProcessedData

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """당신은 단말기 FA(Field Action) 지원 전문가입니다.
주어진 단말기 정보와 서비스 이력을 바탕으로 FA 담당자에게 유용한 분석을 제공합니다.

분석 시 다음 사항을 포함하세요:
- 단말기 현재 상태 요약
- 주목할 만한 서비스 이력 패턴
- FA 처리 시 권장 조치사항

응답은 간결하고 실용적인 한국어로 작성하세요."""


class AgentClient:
    """Anthropic Claude API와 통신하는 클라이언트입니다."""

    def __init__(self):
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
        )

    async def analyze(self, processed: ProcessedData) -> str:
        """
        가공된 단말기 데이터를 Claude API로 분석하고 결과를 반환합니다.

        Args:
            processed: DataProcessor가 생성한 ProcessedData

        Returns:
            Claude의 분석 텍스트
        """
        if processed.error and not processed.summary_text:
            return f"데이터 조회 중 오류가 발생했습니다: {processed.error}"

        if not processed.ai_prompt:
            return processed.summary_text or "조회된 데이터가 없습니다."

        try:
            logger.info(f"Claude API 요청 - SN: {processed.sn}")

            async with self._client.messages.stream(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=settings.ANTHROPIC_MAX_TOKENS,
                thinking={"type": "adaptive"},
                system=_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": processed.ai_prompt}
                ],
            ) as stream:
                final_message = await stream.get_final_message()

            result = "".join(
                block.text
                for block in final_message.content
                if block.type == "text"
            )

            if not result:
                logger.warning(f"Claude 응답이 비어 있습니다 - SN: {processed.sn}")
                return self._fallback_response(processed)

            logger.info(f"Claude API 응답 수신 완료 - SN: {processed.sn}")
            return result

        except anthropic.AuthenticationError:
            logger.error("Anthropic API 키가 올바르지 않습니다. .env의 ANTHROPIC_API_KEY를 확인하세요.")
            return self._fallback_response(processed)
        except anthropic.RateLimitError:
            logger.error(f"Anthropic API 호출 한도 초과 - SN: {processed.sn}")
            return self._fallback_response(processed)
        except anthropic.BadRequestError as e:
            logger.error(f"Anthropic API 잘못된 요청: {e} - SN: {processed.sn}")
            return self._fallback_response(processed)
        except anthropic.APIError as e:
            logger.error(f"Anthropic API 오류: {e} - SN: {processed.sn}")
            return self._fallback_response(processed)
        except Exception as e:
            logger.error(f"Claude API 통신 중 예외 발생: {e} - SN: {processed.sn}")
            return self._fallback_response(processed)

    @staticmethod
    def _fallback_response(processed: ProcessedData) -> str:
        """Claude API 연결 실패 시 DB 조회 결과만으로 응답합니다."""
        return (
            f"[AI 분석 서비스 연결 실패]\n\n"
            f"아래는 데이터베이스 조회 결과입니다:\n\n"
            f"{processed.summary_text}"
        )

    async def close(self):
        await self._client.close()


# 싱글턴 인스턴스
agent_client = AgentClient()
