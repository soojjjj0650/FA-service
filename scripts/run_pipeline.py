"""
FA Pipeline - Mail Download + SN Query

Steps:
  1. Download FA Excel attachments from samsung.net mail
  2. Extract SNs from Excel, run Superset queries
  3. Save result CSVs

Usage:
    python scripts/run_pipeline.py
"""

import asyncio
import ctypes
import logging
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _prevent_sleep():
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED


def _allow_sleep():
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)  # ES_CONTINUOUS


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def find_latest_excel(folder: Path) -> Path | None:
    files = list(folder.glob("*.xlsx")) + list(folder.glob("*.xls")) + list(folder.glob("*.xlsm"))
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)


async def main():
    _prevent_sleep()

    print("=" * 60)
    print("  FA Pipeline - Mail Download + SN Query")
    print("=" * 60)
    print()

    # Step 1: Mail download
    print("[1/2] Downloading mail attachments...")
    downloaded_files = []
    try:
        from app.scraper.mail_downloader import download_mail_attachments
        downloaded_files = await download_mail_attachments()
        if downloaded_files:
            print(f"  -> {len(downloaded_files)} file(s) downloaded:")
            for f in downloaded_files:
                print(f"      {f}")
        else:
            print("  -> No new attachments found")
    except Exception as e:
        print(f"  [ERROR] Mail download failed: {e}")
        traceback.print_exc()
        _allow_sleep()
        print()
        input("  Press any key to close...")
        return

    print()

    # Step 2: Find Excel file
    print("[2/2] Running SN queries...")
    from app.config import settings

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
        print(f"  [ERROR] Excel file not found.")
        print(f"  Search path: {fa_data_dir}")
        _allow_sleep()
        print()
        input("  Press any key to close...")
        return

    print(f"  -> Excel: {excel_path}")
    print()

    # Step 3: Run batch queries
    try:
        from run_batch import main as run_batch_main
        sys.argv = ["run_batch.py", str(excel_path)]
        await run_batch_main()
    except Exception as e:
        print(f"  [ERROR] Query failed: {e}")
        traceback.print_exc()

    _allow_sleep()
    print()
    input("  Press any key to close...")


if __name__ == "__main__":
    asyncio.run(main())
