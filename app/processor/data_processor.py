"""
Data Processor - SQL 쿼리 결과를 AI Agent에 보내기 적합한 형태로 가공

처리 내용:
  - 빈 값 정리
  - 날짜 포맷 통일
  - 단말기 정보 요약 구조 생성
  - AI Agent 프롬프트 생성
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.scraper.query_runner import QueryResult

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    """단말기 핵심 정보"""
    sn: str
    model: str = ""
    manufacture_date: str = ""
    firmware_version: str = ""
    status: str = ""

    # 고객 정보
    customer_name: str = ""
    contract_start: str = ""
    contract_end: str = ""
    contract_active: bool = False

    # 서비스 이력 (최근 순)
    service_history: list[dict[str, str]] = field(default_factory=list)

    # 원본 행 수
    raw_row_count: int = 0


@dataclass
class ProcessedData:
    sn: str
    device: DeviceInfo
    summary_text: str          # AI Agent에 보낼 요약 텍스트
    ai_prompt: str             # AI Agent 프롬프트
    error: str | None = None


class DataProcessor:
    """SQL 쿼리 결과를 가공합니다."""

    # 컬럼명 매핑 (포털 컬럼명 → 내부 필드명)
    # 실제 포털 컬럼명에 맞게 수정하세요
    COLUMN_MAP = {
        "serial_number": "sn",
        "device_model": "model",
        "manufacture_date": "manufacture_date",
        "firmware_version": "firmware_version",
        "status": "status",
        "customer_name": "customer_name",
        "contract_start": "contract_start",
        "contract_end": "contract_end",
        "last_service_date": "last_service_date",
        "service_type": "service_type",
        "engineer_name": "engineer_name",
        "service_note": "service_note",
    }

    def process(self, query_result: QueryResult) -> ProcessedData:
        """QueryResult를 ProcessedData로 변환합니다."""

        if not query_result.success:
            device = DeviceInfo(sn=query_result.sn)
            return ProcessedData(
                sn=query_result.sn,
                device=device,
                summary_text="",
                ai_prompt="",
                error=query_result.error,
            )

        if not query_result.rows:
            device = DeviceInfo(sn=query_result.sn)
            return ProcessedData(
                sn=query_result.sn,
                device=device,
                summary_text=f"SN '{query_result.sn}'에 해당하는 기기를 찾을 수 없습니다.",
                ai_prompt="",
                error="데이터 없음",
            )

        device = self._extract_device_info(query_result)
        summary = self._build_summary(device)
        prompt = self._build_ai_prompt(device, summary)

        logger.info(
            f"데이터 가공 완료 - SN: {query_result.sn}, "
            f"서비스 이력: {len(device.service_history)}건"
        )

        return ProcessedData(
            sn=query_result.sn,
            device=device,
            summary_text=summary,
            ai_prompt=prompt,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_device_info(self, result: QueryResult) -> DeviceInfo:
        first = result.rows[0]

        device = DeviceInfo(
            sn=result.sn,
            model=self._get(first, "device_model"),
            manufacture_date=self._format_date(self._get(first, "manufacture_date")),
            firmware_version=self._get(first, "firmware_version"),
            status=self._get(first, "status"),
            customer_name=self._get(first, "customer_name"),
            contract_start=self._format_date(self._get(first, "contract_start")),
            contract_end=self._format_date(self._get(first, "contract_end")),
            raw_row_count=result.row_count,
        )

        # 계약 활성 여부 판단
        device.contract_active = self._is_contract_active(device.contract_end)

        # 서비스 이력 추출 (중복 제거)
        seen = set()
        for row in result.rows:
            svc_date = self._get(row, "last_service_date")
            svc_type = self._get(row, "service_type")
            key = (svc_date, svc_type)
            if key in seen or (not svc_date and not svc_type):
                continue
            seen.add(key)
            device.service_history.append({
                "date": self._format_date(svc_date),
                "type": svc_type,
                "engineer": self._get(row, "engineer_name"),
                "note": self._get(row, "service_note"),
            })

        return device

    def _build_summary(self, device: DeviceInfo) -> str:
        """AI Agent에 전달할 요약 텍스트를 생성합니다."""
        lines = [
            f"=== 단말기 정보 ===",
            f"SN: {device.sn}",
            f"모델: {device.model or '정보 없음'}",
            f"제조일: {device.manufacture_date or '정보 없음'}",
            f"펌웨어: {device.firmware_version or '정보 없음'}",
            f"상태: {device.status or '정보 없음'}",
            "",
            f"=== 고객/계약 정보 ===",
            f"고객명: {device.customer_name or '정보 없음'}",
            f"계약기간: {device.contract_start} ~ {device.contract_end}",
            f"계약 상태: {'활성' if device.contract_active else '만료/없음'}",
            "",
            f"=== 서비스 이력 ({len(device.service_history)}건) ===",
        ]

        if device.service_history:
            for i, svc in enumerate(device.service_history[:10], 1):  # 최근 10건
                lines.append(
                    f"{i}. [{svc['date']}] {svc['type']} - "
                    f"담당: {svc['engineer']} / {svc['note']}"
                )
        else:
            lines.append("서비스 이력 없음")

        return "\n".join(lines)

    def _build_ai_prompt(self, device: DeviceInfo, summary: str) -> str:
        """AI Agent에 보낼 분석 요청 프롬프트를 생성합니다."""
        return (
            f"다음은 FA가 조회한 단말기(SN: {device.sn})의 정보입니다.\n\n"
            f"{summary}\n\n"
            f"위 정보를 바탕으로 다음을 분석해 주세요:\n"
            f"1. 단말기의 현재 상태 요약\n"
            f"2. 계약 및 보증 상태 안내\n"
            f"3. 서비스 이력 요약 및 반복 문제 여부\n"
            f"4. FA에게 전달할 주요 권고사항\n"
            f"\n한국어로 FA가 이해하기 쉽게 간결하게 답변해 주세요."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Utilities
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _get(row: dict[str, Any], key: str) -> str:
        val = row.get(key, "") or ""
        return str(val).strip()

    @staticmethod
    def _format_date(date_str: str) -> str:
        if not date_str:
            return ""
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return date_str

    @staticmethod
    def _is_contract_active(contract_end: str) -> bool:
        if not contract_end:
            return False
        try:
            end_date = datetime.strptime(contract_end, "%Y-%m-%d")
            return end_date >= datetime.now()
        except ValueError:
            return False


# 싱글턴 인스턴스
data_processor = DataProcessor()
