"""
Superset 로그인 스크립트 (1단계 자동 + 2단계 Bio 대기)

동작 순서:
  1. Edge 브라우저 자동 실행
  2. Superset SQL Lab 접속
  3. ID / PW 자동 입력 → Enter
  4. "SingleID Authenticator - Bio" 버튼 자동 클릭
  5. 핸드폰 생체인증 완료 대기 (최대 90초)
  6. /sqllab 페이지 진입 확인 → 세션 저장

사용법:
    python scripts/manual_login.py

세션 만료 시 이 스크립트를 다시 실행하세요.
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from app.config import settings

SESSION_FILE = settings.SESSION_FILE
SESSION_META_FILE = SESSION_FILE.parent / "session_meta.json"

SUPERSET_URL = settings.PORTAL_URL
USERNAME = settings.PORTAL_USERNAME
PASSWORD = settings.PORTAL_PASSWORD
EDGE_PATH = settings.EDGE_EXECUTABLE_PATH


async def manual_login():
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  FA Service - Superset 로그인")
    print("=" * 60)
    print()
    print(f"  URL     : {SUPERSET_URL}")
    print(f"  계정    : {USERNAME}")
    print(f"  브라우저: Edge")
    print()

    # Edge 실행 경로 결정
    edge_path = EDGE_PATH if os.path.exists(EDGE_PATH) else None
    if edge_path:
        print(f"  Edge 경로: {edge_path}")
    else:
        print("  [주의] Edge 경로 없음 → 시스템 Chromium 사용")
    print()

    async with async_playwright() as p:
        launch_kwargs = dict(
            headless=False,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
        )
        if edge_path:
            launch_kwargs["executable_path"] = edge_path

        browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            viewport=None,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
            ),
        )
        page = await context.new_page()

        # ─── 1단계: Superset 접속 + ID/PW 자동 입력 ────────────────────────
        print("1단계: Superset 접속 중...")
        await page.goto(SUPERSET_URL, wait_until="domcontentloaded", timeout=30_000)

        print("1단계: ID / PW 자동 입력 중...")
        try:
            await page.wait_for_selector("#userNameInput", timeout=15_000)
            await page.fill("#userNameInput", USERNAME)
            await page.fill("#passwordInput", PASSWORD)
            await page.keyboard.press("Enter")
            print("       → ID/PW 입력 완료")
        except PlaywrightTimeout:
            print("       [경고] 로그인 페이지 미감지 (현재 URL:", page.url, ")")

        # ─── 2단계: Bio 인증 버튼 클릭 ──────────────────────────────────────
        print()
        print("2단계: Bio 인증 버튼 탐색 중...")
        bio_selectors = [
            'span:has-text("SingleID Authenticator - Bio")',
            'text="SingleID Authenticator - Bio"',
            'span.flex.items-center:has-text("SingleID Authenticator - Bio")',
            '[data-v-d1d0cf9c] span:has-text("SingleID Authenticator - Bio")',
        ]
        bio_clicked = False
        for sel in bio_selectors:
            try:
                await page.wait_for_selector(sel, timeout=10_000)
                await page.click(sel)
                bio_clicked = True
                print(f"       → Bio 버튼 클릭 완료")
                break
            except PlaywrightTimeout:
                continue

        if not bio_clicked:
            print("       [경고] Bio 버튼 자동 클릭 실패")
            print("              브라우저에서 직접 'SingleID Authenticator - Bio'를 선택해 주세요.")

        # ─── 3단계: 생체인증 완료 대기 ──────────────────────────────────────
        print()
        print("3단계: 핸드폰에서 생체인증(지문/Face ID)을 완료해 주세요...")
        print("       SQL Lab 진입 대기 중 (최대 90초)...")
        print()

        try:
            await page.wait_for_url("**/sqllab**", timeout=90_000)
            print("       → SQL Lab 진입 확인!")
        except PlaywrightTimeout:
            current_url = page.url
            if "sqllab" not in current_url:
                print(f"       [경고] 90초 내 SQL Lab 미진입 (현재: {current_url})")
                await asyncio.get_event_loop().run_in_executor(
                    None, input, "       수동으로 SQL Lab 진입 후 Enter를 눌러 주세요: "
                )

        # ─── 세션 저장 ───────────────────────────────────────────────────────
        await context.storage_state(path=str(SESSION_FILE))

        meta = {
            "saved_at": datetime.now().isoformat(),
            "portal_url": page.url,
            "note": "superset auto login - bio mfa",
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
    print("  이제 FA Service를 실행하면 이 세션이 재사용됩니다.")
    print("  세션 만료 시 이 스크립트를 다시 실행하세요.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(manual_login())
