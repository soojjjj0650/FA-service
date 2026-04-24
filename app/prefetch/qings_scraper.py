"""
Qings 스크래퍼 — Playwright로 Qings 사이트에 접속해 엑셀을 다운로드합니다.

SSO 인증: 저장된 auth state(qings_auth_state.json)를 재사용합니다.
          최초 실행 시 QINGS_HEADLESS=false 상태에서 수동 로그인 필요.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Playwright, Page

from app.config import settings

logger = logging.getLogger(__name__)

# ── Nexacro XPath 셀렉터 ──────────────────────────────────────────────────────
_BASE = "mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001.form.div_form.form"

_SEL = {
    # 메인 메뉴 — Korea SVC Data(KR)
    "menu_kr":
        '//*[@id="mainframe.VFrameSet0.IntroFrame.form.div_left.form'
        '.div_lfavorte.form.grd_Notice.body.gridrow_0.cell_0_0:text"]',

    # 날짜 입력 (시작일 Edt_011 추정 / 종료일 Edt_012 확인)
    "date_from":  f'//*[@id="{_BASE}.div_Section1.form.Edt_011:input"]',
    "date_to":    f'//*[@id="{_BASE}.div_Section1.form.Edt_012:input"]',

    # 통합제품 돋보기 + 체크박스
    "mag_product":   f'//*[@id="{_BASE}.div_Section1.form.Img_020:icontext"]',
    "chk_product_0": f'//*[@id="{_BASE}.div_Section2.form.grd_List1.body.gridrow_0.cell_0_1.cellcheckbox:icontext"]',

    # 지수산입구분 돋보기 + 체크박스 2개
    "mag_intype":    f'//*[@id="{_BASE}.div_Section1.form.Img_090:icontext"]',
    "chk_intype_0":  f'//*[@id="{_BASE}.div_Section2.form.grd_List1.body.gridrow_0.cell_0_1.cellcheckbox:icontext"]',
    "chk_intype_1a": f'//*[@id="{_BASE}.div_Section2.form.grd_List1.body.gridrow_1.cell_1_1.cellcheckbox:icontext"]',
    "chk_intype_1b": f'//*[@id="{_BASE}.div_Section2.form.grd_List1.body.gridrow_1.cell_1_1.checkbox"]',

    # 경영유무무상 돋보기 + 체크박스 2개
    "mag_warranty":    f'//*[@id="{_BASE}.div_Section1.form.Img_080:icontext"]',
    "chk_warranty_0":  f'//*[@id="{_BASE}.div_Section2.form.grd_List1.body.gridrow_0.cell_0_1.cellcheckbox:icontext"]',
    "chk_warranty_1a": f'//*[@id="{_BASE}.div_Section2.form.grd_List1.body.gridrow_1.cell_1_1.cellcheckbox:icontext"]',
    "chk_warranty_1b": f'//*[@id="{_BASE}.div_Section2.form.grd_List1.body.gridrow_1.cell_1_1.checkbox"]',

    # 다운 컬럼 전체 + Apply (셀렉터 변형 2가지)
    "btn_all_cols":  f'//*[@id="{_BASE}.div_Section1.form.img_Tab3:icontext"]',
    "btn_apply_a":   '//*[@id="mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001.form.div_left.form.btn_Apply:icontext"]',
    "btn_apply_b":   '//*[@id="mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001.form.div_left.form.btn_Apply"]',
}

_AUTH_STATE_PATH = Path("data") / "sessions" / "qings_auth_state.json"


async def scrape_qings_excel(save_dir: str) -> Optional[str]:
    """
    Qings에서 엑셀을 다운받아 save_dir에 저장하고 파일 경로를 반환합니다.
    실패 시 None 반환.
    """
    os.makedirs(save_dir, exist_ok=True)
    _AUTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    pw: Playwright = await async_playwright().start()
    try:
        # 기존 browser_pool과 동일한 방식으로 브라우저 실행
        launch_kwargs: dict = {
            "headless": settings.QINGS_HEADLESS,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        }
        edge_path = settings.EDGE_EXECUTABLE_PATH
        if edge_path and os.path.exists(edge_path):
            launch_kwargs["executable_path"] = edge_path
            logger.info(f"[Qings] Edge 브라우저 사용: {edge_path}")

        browser = await pw.chromium.launch(**launch_kwargs)

        ctx_kwargs: dict = {
            "accept_downloads": True,
            "viewport": {"width": 1280, "height": 900},
        }
        if _AUTH_STATE_PATH.exists():
            ctx_kwargs["storage_state"] = str(_AUTH_STATE_PATH)

        context = await browser.new_context(**ctx_kwargs)
        page = await context.new_page()

        try:
            url = f"https://{settings.QINGS_URL}"
            logger.info(f"[Qings] 접속 중: {url}")
            # Nexacro는 계속 네트워크 요청을 하므로 domcontentloaded만 대기
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            # Nexacro 앱 초기화 대기
            await asyncio.sleep(5)

            # SSO 리다이렉트 감지
            if any(kw in page.url.lower() for kw in ("login", "sso", "auth")):
                if not settings.QINGS_HEADLESS:
                    logger.warning("[Qings] SSO 로그인 필요 — 브라우저에서 로그인 후 Enter를 누르세요.")
                    input("[Qings] 로그인 완료 후 Enter 입력...")
                    await context.storage_state(path=str(_AUTH_STATE_PATH))
                    logger.info(f"[Qings] Auth state 저장 완료: {_AUTH_STATE_PATH}")
                else:
                    raise RuntimeError(
                        "SSO 로그인 필요. QINGS_HEADLESS=false 설정 후 수동 로그인하세요."
                    )

            # 날짜 계산
            today = datetime.now()
            date_from = (today - timedelta(days=2)).strftime("%Y%m%d")
            date_to   = (today - timedelta(days=1)).strftime("%Y%m%d")

            # ── 1. Korea SVC Data(KR) 클릭 ───────────────────────────────────
            logger.info("[Qings] Korea SVC Data(KR) 클릭")
            await _click(page, _SEL["menu_kr"], timeout=30_000)
            # 클릭 후 화면 전환 대기 (networkidle 대신 고정 sleep)
            await asyncio.sleep(5)

            # ── 2. 날짜 입력 ─────────────────────────────────────────────────
            logger.info(f"[Qings] 시작일 입력: {date_from}")
            await _fill_date(page, _SEL["date_from"], date_from)
            logger.info(f"[Qings] 종료일 입력: {date_to}")
            await _fill_date(page, _SEL["date_to"], date_to)

            # ── 3. 통합제품 선택 ──────────────────────────────────────────────
            logger.info("[Qings] 통합제품 돋보기 클릭")
            await _click(page, _SEL["mag_product"])
            await asyncio.sleep(1)
            await _click(page, _SEL["chk_product_0"])
            await asyncio.sleep(0.5)

            # ── 4. 지수산입구분 선택 ──────────────────────────────────────────
            logger.info("[Qings] 지수산입구분 돋보기 클릭")
            await _click(page, _SEL["mag_intype"])
            await asyncio.sleep(1.5)
            await _click(page, _SEL["chk_intype_0"])
            await asyncio.sleep(1)
            await _click_any_frame(page, _SEL["chk_intype_1a"]) or await _click_any_frame(page, _SEL["chk_intype_1b"])
            await asyncio.sleep(1)

            # ── 5. 경영유무무상 선택 ──────────────────────────────────────────
            logger.info("[Qings] 경영유무무상 돋보기 클릭")
            await _click(page, _SEL["mag_warranty"])
            await asyncio.sleep(1.5)
            await _click(page, _SEL["chk_warranty_0"])
            await asyncio.sleep(1)
            await _click_any_frame(page, _SEL["chk_warranty_1a"]) or await _click_any_frame(page, _SEL["chk_warranty_1b"])
            await asyncio.sleep(1)

            # ── 6. 다운 컬럼 전체 ─────────────────────────────────────────────
            logger.info("[Qings] 다운 컬럼 전체 클릭")
            await _click_any_frame(page, _SEL["btn_all_cols"])
            await asyncio.sleep(2)

            # ── 7. Apply → 엑셀 다운로드 (최대 3분 대기) ─────────────────────
            logger.info("[Qings] Apply 클릭 시도...")
            save_path = os.path.join(
                save_dir, f"qings_{today.strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            # Nexacro는 Windows Downloads 폴더에 저장하므로 두 곳 모두 감시
            win_downloads = str(Path.home() / "Downloads")
            before_save  = _snapshot_xlsx(save_dir)
            before_dl    = _snapshot_xlsx(win_downloads)

            # Apply 버튼: 모든 프레임 순회 + JS 직접 클릭 fallback
            clicked = await _click_any_frame(page, _SEL["btn_apply_a"])
            if not clicked:
                clicked = await _click_any_frame(page, _SEL["btn_apply_b"])
            if not clicked:
                logger.warning("[Qings] XPath 실패 → JS 직접 클릭 시도")
                clicked = await _js_click(page, [
                    "mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001.form.div_left.form.btn_Apply:icontext",
                    "mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001.form.div_left.form.btn_Apply",
                ])
            if not clicked:
                raise RuntimeError("Apply 버튼을 찾지 못했습니다. 셀렉터를 확인하세요.")

            logger.info("[Qings] Apply 클릭 완료 — 다운로드 대기 중 (최대 3분)...")
            # save_dir 먼저, 없으면 Windows Downloads 폴더 감시
            found = await _wait_new_xlsx(save_dir, before_save, timeout=30)
            if not found:
                logger.info(f"[Qings] save_dir에 없음 → Downloads 폴더 감시: {win_downloads}")
                found = await _wait_new_xlsx(win_downloads, before_dl, timeout=150)
            if found:
                import shutil
                shutil.copy2(found, save_path)
                logger.info(f"[Qings] 다운로드 완료: {found} → {save_path}")

            # auth state 갱신
            await context.storage_state(path=str(_AUTH_STATE_PATH))
            return save_path

        except Exception as e:
            logger.error(f"[Qings] 스크래핑 오류: {type(e).__name__}: {e}", exc_info=True)
            return None
        finally:
            await browser.close()
    finally:
        await pw.stop()


def _snapshot_xlsx(folder: str) -> set:
    """폴더 내 xlsx 파일 목록 스냅샷."""
    p = Path(folder)
    if not p.exists():
        return set()
    return {str(f) for f in p.glob("*.xlsx")}


async def _wait_new_xlsx(folder: str, before: set, timeout: int = 180) -> Optional[str]:
    """새로 생긴 xlsx 파일이 나타날 때까지 대기."""
    for _ in range(timeout):
        after = _snapshot_xlsx(folder)
        new = after - before
        if new:
            return sorted(new, key=lambda f: Path(f).stat().st_mtime)[-1]
        await asyncio.sleep(1)
    return None


async def _click(page: Page, xpath: str, timeout: int = 10_000):
    """메인 프레임에서 XPath 클릭."""
    await page.locator(f"xpath={xpath}").click(timeout=timeout)


async def _click_any_frame(page: Page, xpath: str, timeout: int = 5_000) -> bool:
    """메인 프레임 + 모든 자식 프레임에서 XPath 요소를 찾아 클릭합니다."""
    for frame in page.frames:
        try:
            loc = frame.locator(f"xpath={xpath}")
            if await loc.count() > 0:
                await loc.first.click(timeout=timeout)
                logger.info(f"[Qings] 클릭 성공 (frame: {frame.name or frame.url[:40]})")
                return True
        except Exception:
            continue
    return False


async def _js_click(page: Page, element_ids: list[str]) -> bool:
    """모든 프레임에서 JS getElementById로 클릭 시도."""
    for frame in page.frames:
        for eid in element_ids:
            try:
                result = await frame.evaluate(
                    f"() => {{ const el = document.getElementById({repr(eid)}); "
                    f"if (el) {{ el.click(); return true; }} return false; }}"
                )
                if result:
                    logger.info(f"[Qings] JS 클릭 성공: {eid}")
                    return True
            except Exception:
                continue
    return False


async def _fill_date(page: Page, xpath: str, date_str: str):
    """날짜 입력 필드를 채웁니다."""
    loc = page.locator(f"xpath={xpath}")
    await loc.click()
    await loc.fill("")
    await loc.type(date_str, delay=50)
    await page.keyboard.press("Tab")
    await asyncio.sleep(0.3)
