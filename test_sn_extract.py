"""
SN 추출 테스트 스크립트

실행:
  python test_sn_extract.py                        # CSV_DOWNLOAD_PATH 에서 최신 xlsx 자동 탐색
  python test_sn_extract.py C:/path/to/file.xls    # 파일 직접 지정
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from app.config import settings
from app.prefetch.prefetch_runner import extract_sns_from_excel


def find_latest_excel(folder: str) -> str | None:
    p = Path(folder)
    files = list(p.glob("*.xlsx")) + list(p.glob("*.xls"))
    if not files:
        return None
    return str(max(files, key=lambda f: f.stat().st_mtime))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        excel_path = sys.argv[1]
    else:
        excel_path = find_latest_excel(settings.CSV_DOWNLOAD_PATH)

    if not excel_path or not Path(excel_path).exists():
        print(f"❌ 엑셀 파일을 찾을 수 없습니다.")
        print(f"   탐색 경로: {settings.CSV_DOWNLOAD_PATH}")
        print(f"   또는 직접 지정: python test_sn_extract.py 파일경로.xlsx")
        sys.exit(1)

    from datetime import date, timedelta
    cutoff = (date.today() - timedelta(days=settings.QINGS_DATE_LOOKBACK_DAYS)).strftime("%Y%m%d")

    print(f"파일: {excel_path}")
    print(f"SN 열: {settings.QINGS_SN_COLUMN}")
    print(f"날짜 열: {settings.QINGS_DATE_COLUMN}")
    print(f"기준일: {cutoff} 이후 ({settings.QINGS_DATE_LOOKBACK_DAYS}일)")
    print()

    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    sns = extract_sns_from_excel(excel_path)

    print()
    print("=" * 50)
    if sns:
        print(f"✅ SN {len(sns)}개 추출 완료")
        print(f"   처음 10개: {sns[:10]}")
    else:
        print("❌ SN 추출 실패 — 열 이름 확인 필요")
    print("=" * 50)
