"""
Knox 운영 환경에서 사용자 ID 검색
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings

async def main():
    import httpx

    base_url = settings.KNOX_MESSENGER_BASE_URL.rstrip("/")
    headers = {
        "Authorization": f"Bearer {settings.KNOX_ACCESS_TOKEN}",
        "System-ID": settings.KNOX_SYSTEM_ID,
        "x-device-id": settings.KNOX_DEVICE_ID,
        "x-device-type": "relation",
        "Accept": "application/json",
    }

    search_id = input("Samsung ID 입력 (예: sujin06.bae): ").strip()

    # Knox contact search endpoints 시도
    endpoints = [
        f"/messenger/contact/api/v2.0/contact/search?keyword={search_id}",
        f"/messenger/contact/api/v2.0/contact/search?query={search_id}",
        f"/messenger/contact/api/v2.0/user/search?keyword={search_id}",
        f"/messenger/contact/api/v2.0/contact?employeeId={search_id}",
        f"/messenger/contact/api/v2.0/contact?loginId={search_id}",
    ]

    async with httpx.AsyncClient(timeout=10, verify=False) as client:
        for ep in endpoints:
            url = base_url + ep
            try:
                resp = await client.get(url, headers=headers)
                print(f"\n[{resp.status_code}] {ep}")
                print(resp.text[:500])
            except Exception as e:
                print(f"\n[ERR] {ep}: {e}")

    print()
    input("Press any key to close...")

if __name__ == "__main__":
    asyncio.run(main())
