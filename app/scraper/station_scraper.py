"""
Station Client - 기지국 정보 조회 (10.246.56.50:8000/api/stations)

흐름:
  1. GET /api/stations 전체 목록 조회
  2. operator / TAC / PCI 로 필터링
  3. 결과 반환
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

STATION_API_URL = "http://10.246.56.50:8000/api/stations"

# PLMN → API operator 값 매핑
PLMN_OPERATOR: dict[str, str] = {
    "45005": "SKT",
    "45006": "LGU",
    "45008": "KT",
}

# 내부 입력값 → API operator 값 정규화
OPERATOR_MAP: dict[str, str] = {
    "skt":  "SKT",
    "kt":   "KT",
    "lgu":  "LGU",
    "lgu+": "LGU",
    "lg":   "LGU",
    "SKT":  "SKT",
    "KT":   "KT",
    "LGU":  "LGU",
}


@dataclass
class StationResult:
    operator: str
    tac: str
    pci: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    success: bool = True
    error: str | None = None

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def to_text(self) -> str:
        """챗봇 표시용 텍스트 - 전체 필드, 주차별 구분"""
        if not self.success:
            return f"기지국 조회 실패: {self.error}"
        if not self.rows:
            return f"[{self.operator} TAC:{self.tac} PCI:{self.pci}] 조회 결과 없음"

        lines = []
        for r in self.rows:
            week  = r.get('week', '-')
            year  = r.get('year', '-')
            lines.append(
                f"{year}년 {week}주차 | "
                f"operator:{r.get('operator','-')} | "
                f"TAC:{r.get('tac','-')} | "
                f"PCI:{r.get('pci','-')} | "
                f"DLCh:{r.get('dlch','-')} | "
                f"CID:{r.get('cid','-')} | "
                f"지역:{r.get('region','-')} | "
                f"Vendor:{r.get('vendor','-')} | "
                f"단말:{r.get('device_cnt','-')} | "
                f"호:{r.get('call_cnt','-')} | "
                f"Drop:{r.get('drop_cnt','-')} | "
                f"RLF:{r.get('rlf_cnt','-')} | "
                f"HO실패:{r.get('ho_failure_cnt','-')} | "
                f"NoRTP:{r.get('no_rtp_cnt','-')} | "
                f"이슈율:{r.get('total_issue_rate','-')} | "
                f"이상점수:{r.get('anomaly_score','-')}"
            )
        return "\n".join(lines)


class StationScraper:
    """GET /api/stations에서 operator·TAC·PCI로 기지국 정보를 조회합니다."""

    async def search(
        self,
        operator: str,
        tac: str,
        pci: str,
    ) -> StationResult:
        op = OPERATOR_MAP.get(operator.strip(), operator.strip().upper())
        logger.info(f"기지국 조회 - operator:{op} TAC:{tac} PCI:{pci}")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(STATION_API_URL)
                resp.raise_for_status()
                all_stations: list[dict] = resp.json()

            # operator / TAC / PCI 필터링
            matched = [
                s for s in all_stations
                if str(s.get("operator", "")).upper() == op
                and str(s.get("tac", "")).strip() == str(tac).strip()
                and str(s.get("pci", "")).strip() == str(pci).strip()
            ]

            # 디버그: 검색 조건과 비슷한 항목 샘플 출력
            samples = [
                s for s in all_stations
                if str(s.get("operator", "")).upper() == op
                and str(s.get("tac", "")).strip() == str(tac).strip()
            ][:3]
            logger.info(
                f"기지국 검색 조건 → operator:{op} TAC:'{tac}' PCI:'{pci}' | "
                f"TAC 매칭 샘플(PCI 무관): {[(s.get('tac'), s.get('pci')) for s in samples]}"
            )
            if matched:
                matched.sort(key=lambda s: (s.get("year", 0), s.get("week", 0)), reverse=True)
                matched = matched[:1]

            logger.info(f"기지국 조회 완료: 전체 {len(all_stations)}건 중 {len(matched)}건 매칭")
            return StationResult(operator=op, tac=tac, pci=pci, rows=matched)

        except Exception as e:
            logger.error(f"기지국 API 조회 실패: {e}")
            return StationResult(operator=op, tac=tac, pci=pci, success=False, error=str(e))


# 싱글턴 인스턴스
station_scraper = StationScraper()
