"""
Data Processor 단독 테스트 스크립트

사용법:
  python scripts/test_data_processor.py                   # CSV_DOWNLOAD_PATH 내 최신 CSV 자동 탐색
  python scripts/test_data_processor.py <CSV파일경로>      # 특정 CSV 파일 지정
  python scripts/test_data_processor.py <SN>              # SN으로 파일 탐색 (예: R3CR3019MEF)

결과:
  - 콘솔에 집계 테이블 출력
  - 동일 폴더에 _processor_result.txt 저장
"""

import csv
import glob
import os
import sys

# ── 경로 설정 (프로젝트 루트를 PYTHONPATH에 추가) ──────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.processor.data_processor import DataProcessor, FEATURE_COLUMNS, FEATURE_AGGREGATION

CSV_DOWNLOAD_PATH = r"C:\Users\sujin06.bae\Desktop\FA_Service_data"
SEP = "=" * 80


def find_csv(arg: str | None) -> str:
    """CSV 파일 경로를 결정합니다."""
    # 직접 경로
    if arg and os.path.isfile(arg):
        return arg

    search_dir = CSV_DOWNLOAD_PATH

    # SN으로 탐색
    if arg:
        pattern = os.path.join(search_dir, f"*{arg}*.csv")
        matches = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
        if matches:
            return matches[0]
        print(f"[경고] '{arg}' 패턴의 CSV를 찾지 못했습니다. 최신 파일로 대체합니다.")

    # 최신 CSV 자동 탐색
    pattern = os.path.join(search_dir, "*.csv")
    matches = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    if matches:
        return matches[0]

    sys.exit(f"[오류] {search_dir} 에서 CSV 파일을 찾을 수 없습니다.")


def read_csv(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rows.append(dict(row))
    return rows


def print_table(feature: str, columns: list[str], rows: list[list[str]]) -> str:
    """컬럼 너비에 맞춘 텍스트 테이블을 반환합니다."""
    if not rows:
        return f"[{feature}] 데이터 없음\n"

    # 컬럼별 최대 너비 계산
    widths = [len(c) for c in columns]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))

    def fmt_row(vals):
        return "  ".join(str(v).ljust(widths[i]) for i, v in enumerate(vals))

    header = fmt_row(columns)
    divider = "  ".join("-" * w for w in widths)
    lines = [
        f"[{feature}]  집계 {len(rows)}건",
        header,
        divider,
    ] + [fmt_row(r) for r in rows]
    return "\n".join(lines)


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    csv_path = find_csv(arg)

    print(SEP)
    print(f"  CSV 파일 : {csv_path}")
    print(SEP)

    raw_rows = read_csv(csv_path)
    print(f"  원본 행수 : {len(raw_rows)}")

    # feature 분포 출력
    feat_count: dict[str, int] = {}
    for r in raw_rows:
        f = str(r.get("feature", "")).strip().upper()
        if f:
            feat_count[f] = feat_count.get(f, 0) + 1
    print(f"  Feature 분포: {feat_count}")
    print()

    # ── DataProcessor 실행 ──────────────────────────────────────────────────
    # QueryResult mock
    class _FakeResult:
        success = True
        sn = os.path.basename(csv_path).replace(".csv", "")
        rows: list = []
        error = None
        csv_path = None

    fake = _FakeResult()
    fake.csv_path = csv_path
    # sn: 파일명에서 추출 (첫 번째 '_' 이전 부분)
    base = os.path.basename(csv_path).replace(".csv", "")
    fake.sn = base.split("_")[0] if "_" in base else base

    dp = DataProcessor()
    processed = dp.process(fake)

    # ── 결과 출력 ──────────────────────────────────────────────────────────
    output_lines = []
    output_lines.append(SEP)
    output_lines.append(f"  SN: {processed.sn}   |   feature 수: {len(processed.feature_tables)}")
    output_lines.append(SEP)

    for feat, table in processed.feature_tables.items():
        agg_cfg = FEATURE_AGGREGATION.get(feat, {})
        group_by  = agg_cfg.get("group_by", [])
        sum_cols  = agg_cfg.get("sum", [])
        avg_cols  = agg_cfg.get("avg", [])
        sort_col  = agg_cfg.get("sort_by", "")

        output_lines.append(f"\n{'─'*60}")
        output_lines.append(f"  Feature : {feat}")
        if group_by:
            output_lines.append(f"  GroupBy : {', '.join(group_by)}")
        if sum_cols:
            output_lines.append(f"  합계    : {', '.join(sum_cols)}")
        if avg_cols:
            output_lines.append(f"  평균    : {', '.join(avg_cols)}")
        if sort_col:
            output_lines.append(f"  정렬    : {sort_col} 내림차순")
        output_lines.append(f"{'─'*60}")
        output_lines.append(print_table(feat, table.columns, table.rows))

    result_text = "\n".join(output_lines)
    print(result_text)

    # ── 결과 파일 저장 ─────────────────────────────────────────────────────
    result_path = csv_path.replace(".csv", "_processor_result.txt")
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(result_text)

    print(f"\n{SEP}")
    print(f"  결과 저장 완료: {result_path}")
    print(SEP)


if __name__ == "__main__":
    main()
