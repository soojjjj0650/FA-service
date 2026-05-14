"""
FA 미결건 메일 다운로드 단독 실행 스크립트

사용법:
    python scripts/run_mail_download.py
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.scraper.mail_downloader import download_mail_attachments


async def main():
    print("=" * 60)
    print("  FA 미결건 메일 첨부파일 다운로드")
    print("=" * 60)
    print()

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


if __name__ == "__main__":
    asyncio.run(main())
