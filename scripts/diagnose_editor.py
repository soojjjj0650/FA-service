"""
SQL Lab 에디터 진단 스크립트

어떤 에디터(Ace / CodeMirror)가 사용되는지 확인하고
실제 사용 가능한 CSS 셀렉터를 출력합니다.

사용법:
    python scripts/diagnose_editor.py
"""

import asyncio
import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from app.config import settings

SESSION_FILE = settings.SESSION_FILE
SUPERSET_URL = settings.PORTAL_URL
EDGE_PATH = settings.EDGE_EXECUTABLE_PATH


async def diagnose():
    print("=" * 60)
    print("  SQL Lab 에디터 진단")
    print("=" * 60)

    if not SESSION_FILE.exists():
        print("[오류] 세션 파일 없음. 먼저 login.bat 실행 후 재시도.")
        return

    async with async_playwright() as p:
        launch_kwargs = dict(headless=False, args=["--start-maximized"])
        if os.path.exists(EDGE_PATH):
            launch_kwargs["executable_path"] = EDGE_PATH

        browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            storage_state=str(SESSION_FILE),
            viewport=None,
        )
        page = await context.new_page()

        print(f"\n접속 중: {SUPERSET_URL}")
        await page.goto(SUPERSET_URL, wait_until="domcontentloaded", timeout=30_000)

        try:
            await page.wait_for_load_state("networkidle", timeout=15_000)
        except PlaywrightTimeout:
            pass

        print(f"현재 URL: {page.url}")

        if "login" in page.url.lower():
            print("[오류] 세션 만료됨. login.bat 다시 실행 필요.")
            await browser.close()
            return

        print("\n페이지 로드 완료. 에디터 탐색 중...")
        await asyncio.sleep(3)

        # ─── 에디터 종류 감지 ───────────────────────────────────────────
        result = await page.evaluate("""
            () => {
                const info = {
                    ace: false,
                    codemirror5: false,
                    codemirror6: false,
                    found_selectors: [],
                    all_editors: [],
                };

                // Ace Editor 감지
                if (typeof ace !== 'undefined') {
                    info.ace = true;
                }
                const aceEls = document.querySelectorAll('.ace_editor');
                if (aceEls.length > 0) {
                    info.found_selectors.push('.ace_editor (개수: ' + aceEls.length + ')');
                }

                // CodeMirror 5 감지
                const cm5 = document.querySelectorAll('.CodeMirror');
                if (cm5.length > 0) {
                    info.codemirror5 = true;
                    info.found_selectors.push('.CodeMirror (개수: ' + cm5.length + ')');
                }

                // CodeMirror 6 감지
                const cm6 = document.querySelectorAll('.cm-editor');
                if (cm6.length > 0) {
                    info.codemirror6 = true;
                    info.found_selectors.push('.cm-editor (개수: ' + cm6.length + ')');
                }

                // textarea 감지
                const textareas = document.querySelectorAll('textarea');
                textareas.forEach((t, i) => {
                    const cls = t.className || '(no class)';
                    const id = t.id || '(no id)';
                    info.found_selectors.push('textarea[' + i + '] class=' + cls + ' id=' + id);
                });

                // contenteditable 감지
                const editables = document.querySelectorAll('[contenteditable="true"]');
                if (editables.length > 0) {
                    info.found_selectors.push('[contenteditable] (개수: ' + editables.length + ')');
                }

                return info;
            }
        """)

        print("\n─── 감지 결과 ───────────────────────────────────────")
        print(f"  Ace Editor 전역 객체: {'있음' if result['ace'] else '없음'}")
        print(f"  CodeMirror 5:        {'있음' if result['codemirror5'] else '없음'}")
        print(f"  CodeMirror 6:        {'있음' if result['codemirror6'] else '없음'}")
        print()
        print("  발견된 셀렉터:")
        if result['found_selectors']:
            for sel in result['found_selectors']:
                print(f"    ✓ {sel}")
        else:
            print("    (아무것도 감지되지 않음 - 페이지 로드 미완료 가능)")

        # ─── 스크린샷 저장 ──────────────────────────────────────────────
        screenshot_path = str(ROOT / "data" / "diagnose_screenshot.png")
        os.makedirs(str(ROOT / "data"), exist_ok=True)
        await page.screenshot(path=screenshot_path, full_page=False)
        print(f"\n  스크린샷 저장: {screenshot_path}")

        print()
        print("  브라우저를 확인하고 Enter를 눌러 종료하세요...")
        await asyncio.get_event_loop().run_in_executor(None, input, "")

        await context.close()
        await browser.close()

    print("\n진단 완료!")
    print("위 결과를 Claude에게 알려주세요.")


if __name__ == "__main__":
    asyncio.run(diagnose())
