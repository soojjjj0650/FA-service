"""
FA 전체 파이프라인 단독 실행 스크립트

순서:
  1. Samsung 메일에서 FA 미결건 첨부파일 다운로드
  2. 다운로드된 Excel로 SN 쿼리 실행
  3. 결과 CSV 저장

사용법:
    python scripts/run_pipeline.py
"""

import asyncio
import logging
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def find_latest_excel(folder: Path) -> Path | None:
    """폴더에서 가장 최근 수정된 Excel 파일 탐색"""
    files = list(folder.glob("*.xlsx")) + list(folder.glob("*.xls")) + list(folder.glob("*.xlsm"))
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)


async def main():
    print("=" * 60)
    print("  FA 전체 파이프라인")
    print("  1단계: 메일 첨부파일 다운로드")
    print("  2단계: SN 쿼리 실행 및 결과 저장")
    print("=" * 60)
    print()

    # ── 1단계: 메일 다운로드 ──────────────────────────────────
    print("[1/2] 메일 다운로드 시작...")
    downloaded_files = []
    try:
        from app.scraper.mail_downloader import download_mail_attachments
        downloaded_files = await download_mail_attachments()
        if downloaded_files:
            print(f"  → {len(downloaded_files)}개 파일 다운로드 완료:")
            for f in downloaded_files:
                print(f"      {f}")
        else:
            print("  → 새로운 첨부파일 없음")
    except Exception as e:
        print(f"  [오류] 메일 다운로드 실패: {e}")
        traceback.print_exc()
        print()
        input("  아무 키나 누르면 닫힙니다...")
        return

    print()

    # ── 2단계: Excel 파일 탐색 ───────────────────────────────
    print("[2/2] 쿼리 실행 시작...")
    from app.config import settings

    # 다운로드된 파일 중 Excel이 있으면 최신 것 사용,
    # 없으면 FAdata 폴더에서 최신 Excel 탐색
    excel_path = None

    if downloaded_files:
        excel_files = [
            Path(f) for f in downloaded_files
            if Path(f).suffix.lower() in {".xlsx", ".xls", ".xlsm"}
        ]
        if excel_files:
            excel_path = max(excel_files, key=lambda f: f.stat().st_mtime)

    fa_data_dir = Path(settings.MAIL_SAVE_DIR) if settings.MAIL_SAVE_DIR else \
                  Path(settings.CSV_DOWNLOAD_PATH) / "FAdata"

    if excel_path is None:
        excel_path = find_latest_excel(fa_data_dir)

    if excel_path is None or not excel_path.exists():
        print(f"  [오류] Excel 파일을 찾을 수 없습니다.")
        print(f"  탐색 경로: {fa_data_dir}")
        print()
        input("  아무 키나 누르면 닫힙니다...")
        return

    print(f"  → 사용할 Excel: {excel_path}")
    print()

    # ── 3단계: SN 쿼리 실행 ─────────────────────────────────
    try:
        from run_batch import main as run_batch_main
        sys.argv = ["run_batch.py", str(excel_path)]
        await run_batch_main()
    except Exception as e:
        print(f"  [오류] 쿼리 실행 실패: {e}")
        traceback.print_exc()

    print()
    input("  아무 키나 누르면 닫힙니다...")


if __name__ == "__main__":
    asyncio.run(main())
