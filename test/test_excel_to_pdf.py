"""
Excel/CSV -> Analysis HTML -> PDF / ZIP conversion test

Usage:
  python test/test_excel_to_pdf.py <csv_or_excel_path> [SN] [--zip]

Examples:
  python test/test_excel_to_pdf.py userdata/SN123_inputdata.csv
  python test/test_excel_to_pdf.py userdata/SN123_inputdata.csv SN123 --zip
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def excel_to_csv(excel_path: str, out_dir: str, sn: str) -> str | None:
    """Excel -> CSV conversion."""
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
        print(f"  Excel -> CSV: {csv_path}")
        return csv_path
    except Exception as e:
        print(f"  Excel conversion failed: {e}")
        return None


async def run(input_path: str, sn: str | None = None, make_zip: bool = False):
    from app.analysis.runner import generate_analysis_html
    from app.analysis.pdf_generator import html_to_pdf, html_to_zip

    if not os.path.exists(input_path):
        print(f"File not found: {input_path}")
        return

    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test", "output")
    os.makedirs(out_dir, exist_ok=True)

    if not sn:
        basename = os.path.splitext(os.path.basename(input_path))[0]
        sn = basename.replace("_inputdata", "").replace("_analysis", "")
    print(f"SN: {sn}")

    ext = os.path.splitext(input_path)[1].lower()
    if ext in (".xlsx", ".xls"):
        print("Converting Excel -> CSV...")
        csv_path = excel_to_csv(input_path, out_dir, sn)
        if not csv_path:
            return
    else:
        csv_path = input_path
        print(f"CSV: {csv_path}")

    # Step 1: HTML
    print("\n[1/2] Generating analysis HTML...")
    html_path = generate_analysis_html(sn, csv_path, out_dir)
    if not html_path:
        print("  HTML generation failed")
        return
    html_kb = os.path.getsize(html_path) // 1024
    print(f"  HTML: {html_path} ({html_kb} KB)")

    if make_zip:
        # Step 2a: ZIP
        print("\n[2/2] Creating ZIP...")
        zip_path = os.path.join(out_dir, f"{sn}_analysis.zip")
        ok = html_to_zip(html_path, zip_path, sn)
        if ok:
            zip_kb = os.path.getsize(zip_path) // 1024
            print(f"  ZIP: {zip_path} ({zip_kb} KB)")
            print(f"\nDone! ZIP: {os.path.abspath(zip_path)}")
        else:
            print("  ZIP creation failed")
    else:
        # Step 2b: PDF
        print("\n[2/2] Converting to PDF...")
        pdf_path = os.path.join(out_dir, f"{sn}_analysis.pdf")
        ok = await html_to_pdf(html_path, pdf_path)
        if ok:
            pdf_kb = os.path.getsize(pdf_path) // 1024
            print(f"  PDF: {pdf_path} ({pdf_kb} KB)")
            print(f"\nDone! PDF: {os.path.abspath(pdf_path)}")
        else:
            print("  PDF conversion failed")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_file = sys.argv[1]
    args = sys.argv[2:]
    make_zip = "--zip" in args
    sn_args = [a for a in args if not a.startswith("--")]
    sn_arg = sn_args[0] if sn_args else None

    asyncio.run(run(input_file, sn_arg, make_zip))
