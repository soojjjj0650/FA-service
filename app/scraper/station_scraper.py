"""
Station Client - 기지국 정보 조회 (10.246.56.50:8000/api/stations)

흐름:
  1. GET /api/stations?operator=<op> 조회 (operator별 캐시 1시간)
  2. TAC / PCI 로 필터링
  3. 최근 주차 1건 반환
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

STATION_API_URL = "http://10.246.56.50:8000/api/stations"

# PLMN → 정규화 operator
PLMN_OPERATOR: dict[str, str] = {
    "45005": "SKT",
    "45006": "LGU",
    "45008": "KT",
}

# 입력값 → 정규화 operator
OPERATOR_MAP: dict[str, str] = {
    "skt":   "SKT",
    "kt":    "KT",
    "ktf":   "KT",
    "lgu":   "LGU",
    "lgu+":  "LGU",
    "lg":    "LGU",
    "lg u+": "LGU",
    "SKT":   "SKT",
    "KT":    "KT",
    "KTF":   "KT",
    "LGU":   "LGU",
    "LGU+":  "LGU",
    "LG":    "LGU",
}

# API에서 실제로 사용하는 operator 문자열 후보 (정규화 → 실제값 목록)
# check_api.bat [16]번 결과 확인 후 업데이트 가능
API_OPERATOR_VARIANTS: dict[str, list[str]] = {
    "SKT": ["SKT", "skt"],
    "KT":  ["KT", "kt", "KTF", "ktf"],
    "LGU": ["LGU", "LGU+", "LG U+", "lgu", "lgu+", "LG", "lg"],
}


def _normalize_operator(raw: str) -> str:
    """API에서 받은 operator 값을 SKT/KT/LGU 중 하나로 정규화합니다."""
    v = raw.strip()
    return OPERATOR_MAP.get(v, OPERATOR_MAP.get(v.upper(), v.upper()))


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
        """챗봇 표시용 텍스트 - 전체 필드"""
        if not self.success:
            return f"기지국 조회 실패: {self.error}"
        if not self.rows:
            return f"[{self.operator} TAC:{self.tac} PCI:{self.pci}] 조회 결과 없음"

        lines = []
        for r in self.rows:
            lines.append(
                f"{r.get('year','-')}년 {r.get('week','-')}주차 | "
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

    # operator별 캐시 ({"SKT": [...], "KT": [...], "LGU": [...]})
    _cache: dict[str, list[dict]] = {}
    _cache_time: dict[str, float] = {}
    _CACHE_TTL: float = 3600.0  # 1시간

    async def _get_stations(self, op: str) -> list[dict]:
        """operator별 기지국 목록을 반환합니다. 1시간 캐시 적용."""
        now = time.time()
        if op in self._cache and (now - self._cache_time.get(op, 0)) < self._CACHE_TTL:
            logger.debug(f"기지국 캐시 사용 [{op}] ({len(self._cache[op])}건)")
            return self._cache[op]

        logger.info(f"기지국 목록 갱신 중 [{op}]...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(STATION_API_URL, params={"operator": op})
            resp.raise_for_status()
            data: list[dict] = resp.json()

        # API가 파라미터를 무시하고 전체 반환할 경우 client-side 필터링
        variants = API_OPERATOR_VARIANTS.get(op, [op])
        filtered = [s for s in data if str(s.get("operator", "")).strip() in variants]

        # 필터링 결과가 없으면 정규화 비교로 재시도
        if not filtered:
            filtered = [s for s in data if _normalize_operator(str(s.get("operator", ""))) == op]

        StationScraper._cache[op] = filtered
        StationScraper._cache_time[op] = now
        logger.info(f"기지국 캐시 갱신 완료 [{op}]: 전체 {len(data)}건 → {len(filtered)}건")
        return filtered

    async def search(self, operator: str, tac: str, pci: str) -> StationResult:
        op = OPERATOR_MAP.get(operator.strip(), operator.strip().upper())
        logger.info(f"기지국 조회 - operator:{op} TAC:{tac} PCI:{pci}")

        try:
            stations = await self._get_stations(op)

            matched = [
                s for s in stations
                if str(s.get("tac", "")).strip() == str(tac).strip()
                and str(s.get("pci", "")).strip() == str(pci).strip()
            ]

            if matched:
                matched.sort(key=lambda s: (s.get("year", 0), s.get("week", 0)), reverse=True)
                matched = matched[:1]

            logger.info(f"기지국 조회 완료 [{op}]: {len(stations)}건 중 {len(matched)}건 매칭")
            return StationResult(operator=op, tac=tac, pci=pci, rows=matched)

        except Exception as e:
            logger.error(f"기지국 API 조회 실패: {e}")
            return StationResult(operator=op, tac=tac, pci=pci, success=False, error=str(e))


# 싱글턴 인스턴스
station_scraper = StationScraper()
