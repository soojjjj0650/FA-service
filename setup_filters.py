"""
filter.xlsx를 읽어서 filters.json을 자동으로 채웁니다.

filter.xlsx 형식 (각 열에 값 목록):
  A열: 수리형태
  B열: 지표표준제품코드 (ST_PROD_I)
  C열: GPA_CE
"""
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

FILTER_XLSX = Path(__file__).parent / "filter.xlsx"
FILTERS_JSON = Path(__file__).parent / "filters.json"

COLUMN_MAP = {
    0: ("수리형태",   "수리형태"),
    1: ("ST_PROD_I", "지표표준제품코드"),
    2: ("GPA_CE",    "GPA_CE"),
}


def read_values(xlsx_path: Path) -> dict:
    import openpyxl
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active

    result = {}
    for col_idx, (key, col_name) in COLUMN_MAP.items():
        values = []
        for row in ws.iter_rows(min_row=1, min_col=col_idx+1, max_col=col_idx+1, values_only=True):
            v = row[0]
            if v is not None and str(v).strip():
                values.append(str(v).strip())
        result[key] = (col_name, values)

    wb.close()
    return result


if __name__ == "__main__":
    if not FILTER_XLSX.exists():
        print(f"[ERROR] 파일 없음: {FILTER_XLSX}")
        print("filter.xlsx를 FA-service 폴더에 넣어주세요.")
        input("Enter 키를 눌러 종료...")
        sys.exit(1)

    print(f"읽는 중: {FILTER_XLSX}")
    data = read_values(FILTER_XLSX)

    filters_data = {
        "filters": {},
        "condition": "AND"
    }
    for key, (col_name, values) in data.items():
        filters_data["filters"][key] = {
            "column": col_name,
            "values": values
        }
        print(f"  {key} ({col_name}): {len(values)}개")

    with open(FILTERS_JSON, "w", encoding="utf-8") as f:
        json.dump(filters_data, f, ensure_ascii=False, indent=2)

    print(f"\nfilters.json 저장 완료 → {FILTERS_JSON}")
    input("Enter 키를 눌러 종료...")
