"""
수동 로그인 스크립트

지문인증(MFA)이 있는 포털에 직접 로그인하고 세션을 저장합니다.
서비스 최초 실행 전, 또는 세션 만료 시 이 스크립트를 실행하세요.

사용법:
    python scripts/manual_login.py

동작:
    1. 실제 Chrome 브라우저 창이 열립니다 (headless=False)
    2. 포털 로그인 페이지가 열리면 직접 ID/PW 입력 + 지문인증 진행
    3. 로그인 완료 후 Enter 키를 누르면 세션 저장 후 창이 닫힙니다
    4. 이후 FA 챗봇 서비스가 저장된 세션을 재사용합니다
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 경로에 추가
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright
from app.config import settings


SESSION_FILE = settings.SESSION_FILE
SESSION_META_FILE = SESSION_FILE.parent / "session_meta.json"


async def manual_login():
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  FA 챗봇 - 수동 로그인 (지문인증 포함)")
    print("=" * 60)
    print()
    print("브라우저가 열리면 직접 로그인을 진행해 주세요.")
    print("  1. ID / PW 입력")
    print("  2. 핸드폰 지문인증 완료")
    print("  3. 포털 메인 화면까지 이동 후 이 창에서 Enter 입력")
    print()

    async with async_playwright() as p:
        # 반드시 headless=False — 사용자가 직접 조작해야 함
        browser = await p.chromium.launch(
            headless=False,
            args=["--start-maximized"],
        )
        context = await browser.new_context(
            viewport=None,  # 최대화 모드에서 viewport 자동
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        print(f"포털 접속 중: {settings.PORTAL_LOGIN_URL}")
        await page.goto(settings.PORTAL_LOGIN_URL)

        print()
        print("─" * 60)
        print("브라우저에서 로그인(ID/PW + 지문인증)을 완료해 주세요.")
        print("완료 후 아래에서 Enter 키를 눌러 주세요.")
        print("─" * 60)

        # 사용자가 로그인 완료할 때까지 대기
        await asyncio.get_event_loop().run_in_executor(None, input, "로그인 완료 후 Enter 입력: ")

        # 현재 URL 확인
        current_url = page.url
        if "login" in current_url.lower():
            print()
            print("[경고] 아직 로그인 페이지에 있습니다.")
            print("       로그인을 완료한 후 다시 Enter를 눌러 주세요.")
            await asyncio.get_event_loop().run_in_executor(None, input, "로그인 완료 후 Enter 입력: ")
            current_url = page.url

        # 세션 저장
        await context.storage_state(path=str(SESSION_FILE))

        # 세션 메타데이터 저장 (저장 시간 기록)
        meta = {
            "saved_at": datetime.now().isoformat(),
            "portal_url": current_url,
            "note": "manual login with MFA",
        }
        SESSION_META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

        await context.close()
        await browser.close()

    print()
    print("=" * 60)
    print("  세션 저장 완료!")
    print(f"  저장 위치: {SESSION_FILE}")
    print(f"  저장 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("  이제 FA 챗봇 서비스를 실행하면 이 세션이 재사용됩니다.")
    print("  세션 만료 시 이 스크립트를 다시 실행해 주세요.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(manual_login())
