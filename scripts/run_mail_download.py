"""
FA 미결건 메일 다운로드 단독 실행 스크립트

사용법:
    python scripts/run_mail_download.py
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


IDS_FILE = ROOT / "data" / "sessions" / "mail_downloaded_ids.json"


def reset_ids():
    if IDS_FILE.exists():
        IDS_FILE.unlink()
        print(f"  이력 초기화 완료: {IDS_FILE}")
    else:
        print("  이력 파일 없음 (이미 초기화 상태)")


async def main():
    # --reset 옵션: 다운로드 이력만 삭제하고 종료
    if "--reset" in sys.argv:
        print("=" * 60)
        print("  메일 다운로드 이력 초기화")
        print("=" * 60)
        reset_ids()
        print()
        input("  아무 키나 누르면 닫힙니다...")
        return

    print("=" * 60)
    print("  FA 미결건 메일 첨부파일 다운로드")
    print("=" * 60)
    print()

    try:
        from app.scraper.mail_downloader import download_mail_attachments
        files = await download_mail_attachments()

        print()
        print("=" * 60)
        if files:
            print(f"  완료! {len(files)}개 파일 저장됨:")
            for f in files:
                print(f"    - {f}")
        else:
            print("  완료! 새로운 첨부파일이 없습니다.")
        print("=" * 60)

    except Exception as e:
        print()
        print("=" * 60)
        print(f"  [오류] {e}")
        print()
        traceback.print_exc()
        print("=" * 60)

    print()
    input("  아무 키나 누르면 닫힙니다...")


if __name__ == "__main__":
    asyncio.run(main())
