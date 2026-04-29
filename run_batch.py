"""
SN 배치 쿼리 실행기

실행:
  python run_batch.py                        # CSV_DOWNLOAD_PATH 최신 엑셀 자동 탐색
  python run_batch.py C:/path/to/file.xlsx   # 파일 직접 지정
"""
import sys
import os
import csv
import asyncio
import logging
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from app.config import settings
from app.prefetch.prefetch_runner import extract_sns_from_excel, run_prefetch_for_sns

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("run_batch.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def find_latest_excel(folder: str) -> str | None:
    p = Path(folder)
    files = list(p.glob("*.xlsx")) + list(p.glob("*.xls"))
    if not files:
        return None
    return str(max(files, key=lambda f: f.stat().st_mtime))


async def main():
    if len(sys.argv) > 1:
        excel_path = sys.argv[1]
    else:
        excel_path = find_latest_excel(settings.CSV_DOWNLOAD_PATH)

    if not excel_path or not Path(excel_path).exists():
        print(f"엑셀 파일을 찾을 수 없습니다.")
        print(f"  탐색 경로: {settings.CSV_DOWNLOAD_PATH}")
        sys.exit(1)

    cutoff = (date.today() - timedelta(days=settings.QINGS_DATE_LOOKBACK_DAYS)).strftime("%Y%m%d")
    print(f"파일  : {excel_path}")
    print(f"SN 열 : {settings.QINGS_SN_COLUMN}")
    print(f"날짜  : {cutoff} 이후 ({settings.QINGS_DATE_LOOKBACK_DAYS}일)")
    print()

    sns = extract_sns_from_excel(excel_path)
    if not sns:
        print("SN 추출 실패 — 열 이름 확인 필요")
        sys.exit(1)

    print(f"추출된 SN: {len(sns)}개")
    print(f"저장 경로: {settings.CSV_DOWNLOAD_PATH}")
    print()

    result = await run_prefetch_for_sns(sns)

    # 결과 요약 CSV 저장
    summary_path = Path(settings.CSV_DOWNLOAD_PATH) / f"batch_result_{date.today().strftime('%Y%m%d')}.csv"
    sn_results = result.get("sn_results", [])
    if sn_results:
        with open(summary_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["sn", "status", "detail"])
            writer.writeheader()
            writer.writerows(sn_results)
        logger.info(f"결과 요약 저장 → {summary_path}")

    print()
    print("=" * 60)
    print(f"완료")
    print(f"  전체  : {result.get('total', 0)}개")
    print(f"  캐시  : {result.get('cached', 0)}개 (기존 결과 재사용)")
    print(f"  성공  : {result.get('queried', 0)}개")
    print(f"  실패  : {result.get('failed', 0)}개")
    if result.get("failed_sns"):
        print(f"  실패 SN: {result['failed_sns']}")
    print(f"결과 요약: {summary_path}")
    print(f"CSV 파일 : {settings.CSV_DOWNLOAD_PATH}\\{{SN}}_inputdata.csv")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
