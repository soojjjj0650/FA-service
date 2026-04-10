"""
Code Mappings - 코드값 → 설명 변환

data/code_mappings.xlsx 파일에서 로드합니다.
엑셀 구조:
  A: SIPR,  B: SIPR_Value   (215행)
  C: EMMC,  D: EMMC_Value   (74행)
  E: CAU,   F: CAU_Value
  G: SMBU,  H: SMBU_Value
  I: SAMS,  J: SAMS_Value
  K: MCST,  L: MCST_Value
"""

import logging
import os

logger = logging.getLogger(__name__)

# 코드 → 설명 매핑 (런타임에 로드)
# 구조: {"SIPR": {"200": "call end", "0": "CS Call", ...}, "EMMC": {...}, ...}
CODE_MAPS: dict[str, dict[str, str]] = {}

_EXCEL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "code_mappings.xlsx"
)

# 엑셀 열 쌍 정의: (코드열 인덱스, 값열 인덱스, 매핑키)
_COLUMN_PAIRS = [
    (0, 1, "SIPR"),
    (2, 3, "EMMC"),
    (4, 5, "CAU"),
    (6, 7, "SMBU"),
    (8, 9, "SAMS"),
    (10, 11, "MCST"),
]


def load_code_mappings() -> None:
    """서버 시작 시 엑셀에서 코드 매핑을 로드합니다."""
    path = os.path.abspath(_EXCEL_PATH)
    if not os.path.exists(path):
        logger.warning(f"코드 매핑 파일 없음 (코드 변환 비활성화): {path}")
        return

    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active

        rows = list(ws.iter_rows(min_row=2, values_only=True))  # 1행은 헤더

        for code_col, val_col, key in _COLUMN_PAIRS:
            mapping: dict[str, str] = {}
            for row in rows:
                code = row[code_col] if len(row) > code_col else None
                desc = row[val_col] if len(row) > val_col else None
                if code is not None and desc is not None:
                    mapping[str(code).strip()] = str(desc).strip()
            CODE_MAPS[key] = mapping
            logger.info(f"코드 매핑 로드: {key} ({len(mapping)}개)")

        wb.close()
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
