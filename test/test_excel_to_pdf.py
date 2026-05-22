"""
엑셀/CSV 파일 → 분석 HTML → PDF 변환 테스트

사용법:
  python test/test_excel_to_pdf.py <엑셀파일 또는 CSV파일 경로> [SN번호]

예시:
  python test/test_excel_to_pdf.py userdata/SN123_inputdata.csv
  python test/test_excel_to_pdf.py userdata/FA_data.xlsx SN123456
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def excel_to_csv(excel_path: str, out_dir: str, sn: str) -> str | None:
    """Excel 파일을 CSV로 변환합니다."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
        ws = wb.active
        import csv
        csv_path = os.path.join(out_dir, f"{sn}_inputdata.csv")
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            for row in ws.iter_rows(values_only=True):
                writer.writerow([("" if v is None else str(v)) for v in row])
        wb.close()
        print(f"  Excel → CSV 변환 완료: {csv_path}")
        return csv_path
    except Exception as e:
        print(f"  Excel 변환 실패: {e}")
        return None


async def run(input_path: str, sn: str | None = None):
    from app.analysis.runner import generate_analysis_html
    from app.analysis.pdf_generator import html_to_pdf

    if not os.path.exists(input_path):
        print(f"파일 없음: {input_path}")
        return

    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test", "output")
    os.makedirs(out_dir, exist_ok=True)

    # SN 추출 (인자 없으면 파일명에서 추출)
    if not sn:
        basename = os.path.splitext(os.path.basename(input_path))[0]
        sn = basename.replace("_inputdata", "").replace("_analysis", "")
    print(f"SN: {sn}")

    # 입력 파일 처리
    ext = os.path.splitext(input_path)[1].lower()
    if ext in (".xlsx", ".xls"):
        print("Excel 파일 → CSV 변환 중...")
        csv_path = excel_to_csv(input_path, out_dir, sn)
        if not csv_path:
            return
    else:
        csv_path = input_path
        print(f"CSV 파일 사용: {csv_path}")

    # Step 1: HTML 생성
    print("\n[1/2] 분석 HTML 생성 중...")
    html_path = generate_analysis_html(sn, csv_path, out_dir)
    if not html_path:
        print("  HTML 생성 실패")
        return
    print(f"  HTML 생성 완료: {html_path}")

    # Step 2: PDF 변환
    print("\n[2/2] PDF 변환 중...")
    pdf_path = os.path.join(out_dir, f"{sn}_analysis.pdf")
    ok = await html_to_pdf(html_path, pdf_path)
    if ok:
        size_kb = os.path.getsize(pdf_path) // 1024
        print(f"  PDF 생성 완료: {pdf_path} ({size_kb} KB)")
        print(f"\n완료! PDF 파일: {os.path.abspath(pdf_path)}")
    else:
        print("  PDF 변환 실패")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_file = sys.argv[1]
    sn_arg = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(run(input_file, sn_arg))
