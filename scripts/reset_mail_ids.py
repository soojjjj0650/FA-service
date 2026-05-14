"""다운로드 이력 초기화"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
ids_file = ROOT / "data" / "sessions" / "mail_downloaded_ids.json"

if ids_file.exists():
    ids_file.unlink()
    print(f"삭제 완료: {ids_file}")
else:
    print("이력 파일이 없습니다 (이미 초기화된 상태)")

print()
input("아무 키나 누르면 닫힙니다...")
