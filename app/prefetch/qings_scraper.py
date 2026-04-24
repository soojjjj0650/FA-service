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

    # 다운 컬럼 전체 + Apply
    "btn_all_cols": f'//*[@id="{_BASE}.div_Section1.form.img_Tab3:icontext"]',
    "btn_apply":
        '//*[@id="mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001'
        '.form.div_left.form.btn_Apply:icontext"]',
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
            await _click_fallback(page, _SEL["chk_intype_1a"], _SEL["chk_intype_1b"])
            await asyncio.sleep(1)

            # ── 5. 경영유무무상 선택 ──────────────────────────────────────────
            logger.info("[Qings] 경영유무무상 돋보기 클릭")
            await _click(page, _SEL["mag_warranty"])
            await asyncio.sleep(1.5)
            await _click(page, _SEL["chk_warranty_0"])
            await asyncio.sleep(1)
            await _click_fallback(page, _SEL["chk_warranty_1a"], _SEL["chk_warranty_1b"])
            await asyncio.sleep(1)

            # ── 6. 다운 컬럼 전체 ─────────────────────────────────────────────
            logger.info("[Qings] 다운 컬럼 전체 클릭")
            await _click(page, _SEL["btn_all_cols"])
            await asyncio.sleep(1)

            # ── 7. Apply → 엑셀 다운로드 (최대 3분 대기) ─────────────────────
            logger.info("[Qings] Apply 클릭 — 다운로드 대기 중 (최대 3분)...")
            save_path = os.path.join(
                save_dir, f"qings_{today.strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            async with page.expect_download(timeout=180_000) as dl_info:
                await _click(page, _SEL["btn_apply"])

            download = await dl_info.value
            await download.save_as(save_path)
            logger.info(f"[Qings] 다운로드 완료: {save_path}")

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


async def _click(page: Page, xpath: str, timeout: int = 10_000):
    """XPath 셀렉터로 요소를 클릭합니다."""
    await page.locator(f"xpath={xpath}").click(timeout=timeout)


async def _click_fallback(page: Page, xpath_a: str, xpath_b: str, timeout: int = 5_000):
    """첫 번째 셀렉터 실패 시 두 번째를 시도합니다."""
    try:
        await page.locator(f"xpath={xpath_a}").click(timeout=timeout)
        logger.info(f"[Qings] 클릭 성공 (1번 셀렉터)")
    except Exception:
        logger.warning(f"[Qings] 1번 셀렉터 실패 → 2번 셀렉터 시도")
        await page.locator(f"xpath={xpath_b}").click(timeout=timeout)


async def _fill_date(page: Page, xpath: str, date_str: str):
    """날짜 입력 필드를 채웁니다."""
    loc = page.locator(f"xpath={xpath}")
    await loc.click()
    await loc.fill("")
    await loc.type(date_str, delay=50)
    await page.keyboard.press("Tab")
    await asyncio.sleep(0.3)
