"""
Code Mappings - 코드값 → 설명 변환

data/code_mappings.csv 파일에서 로드합니다.
CSV 구조 (1행=헤더):
  A: SIPR,  B: SIPR_Value
  C: EMMC,  D: EMMC_Value
  E: CAU,   F: CAU_Value
  G: SMBU,  H: SMBU_Value
  I: SAMS,  J: SAMS_Value
  K: MCST,  L: MCST_Value
"""

import csv
import logging
import os

logger = logging.getLogger(__name__)

# 코드 → 설명 매핑 (런타임에 로드)
# 구조: {"SIPR": {"200": "call end", "0": "CS Call", ...}, "EMMC": {...}, ...}
CODE_MAPS: dict[str, dict[str, str]] = {}

_CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "code_mappings.csv"
)

# CSV 열 쌍 정의: (코드열 인덱스, 값열 인덱스, 매핑키)
_COLUMN_PAIRS = [
    (0, 1, "SIPR"),
    (2, 3, "EMMC"),
    (4, 5, "CAU"),
    (6, 7, "SMBU"),
    (8, 9, "SAMS"),
    (10, 11, "MCST"),
]


def load_code_mappings() -> None:
    """서버 시작 시 CSV에서 코드 매핑을 로드합니다."""
    path = os.path.abspath(_CSV_PATH)
    logger.info(f"코드 매핑 파일 경로: {path}")
    if not os.path.exists(path):
        logger.warning(f"코드 매핑 파일 없음 (코드 변환 비활성화): {path}")
        return

    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))

        if not rows:
            return

        data_rows = rows[1:]  # 1행은 헤더

        for code_col, val_col, key in _COLUMN_PAIRS:
            mapping: dict[str, str] = {}
            for row in data_rows:
                code = row[code_col].strip() if len(row) > code_col else ""
                desc = row[val_col].strip() if len(row) > val_col else ""
                if code and desc:
                    mapping[code] = desc
            if mapping:
                CODE_MAPS[key] = mapping
                logger.info(f"코드 매핑 로드: {key} ({len(mapping)}개)")

    except Exception as e:
        logger.error(f"코드 매핑 로드 실패: {e}")


def apply_code(field: str, code: str) -> str:
    """코드값에 설명을 붙여 반환합니다. 매핑 없으면 원본 반환.

    예: apply_code("SIPR", "200") → "200(call end)"
    """
    mapping = CODE_MAPS.get(field)
    if not mapping:
        return code
    desc = mapping.get(code.strip())
    if desc:
        return f"{code}({desc})"
    return code
