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

    # 다운 컬럼 전체
    "btn_all_cols":  f'//*[@id="{_BASE}.div_Section1.form.img_Tab3:icontext"]',

    # 필터 패널 내 검색/적용 버튼 — 돋보기 팝업을 닫을 때 클릭
    "btn_filter_search": '//*[@id="mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001'
                         '.form.div_left.form.div_FormFilter.form.btn_search:icontext"]',

    # Apply 버튼 (메인)
    "btn_apply_exact":   '//*[@id="mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001.form.div_left.form.btn_Apply:icontext"]',
    "btn_apply_nosuffix":'//*[@id="mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001.form.div_left.form.btn_Apply"]',
    "btn_apply_contains":'xpath=//*[contains(@id,"btn_Apply")]',
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
            await _close_filter_panel(page)

            # ── 4. 지수산입구분 선택 ──────────────────────────────────────────
            logger.info("[Qings] 지수산입구분 돋보기 클릭")
            await _click(page, _SEL["mag_intype"])
            await asyncio.sleep(1.5)
            await _click(page, _SEL["chk_intype_0"])
            await asyncio.sleep(1)
            await _click_any_frame(page, _SEL["chk_intype_1a"]) or await _click_any_frame(page, _SEL["chk_intype_1b"])
            await asyncio.sleep(1)
            await _close_filter_panel(page)

            # ── 5. 경영유무무상 선택 ──────────────────────────────────────────
            logger.info("[Qings] 경영유무무상 돋보기 클릭")
            await _click(page, _SEL["mag_warranty"])
            await asyncio.sleep(1.5)
            await _click(page, _SEL["chk_warranty_0"])
            await asyncio.sleep(1)
            await _click_any_frame(page, _SEL["chk_warranty_1a"]) or await _click_any_frame(page, _SEL["chk_warranty_1b"])
            await asyncio.sleep(1)
            await _close_filter_panel(page)

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

            # Nexacro 컴포넌트 경로 / 버튼 DOM ID
            _NX      = "mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001.form.div_left.form.btn_Apply"
            _BTN_ID  = "mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001.form.div_left.form.btn_Apply"
            _ICON_ID = "mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001.form.div_left.form.btn_Apply:icontext"

            # Apply 버튼: 좌표 클릭 > Nexacro API > dispatch_event > force > fallback 순서로 시도
            apply_attempts = [
                ("좌표 마우스클릭(btn)",    lambda: _mouse_position_click(page, _BTN_ID)),
                ("좌표 마우스클릭(icon)",   lambda: _mouse_position_click(page, _ICON_ID)),
                ("Nexacro .click()",        lambda: _nexacro_click(page, _NX)),
                ("Nexacro fireEvent",       lambda: _nexacro_fire_event(page, _NX)),
                ("dispatch_event(icon)",    lambda: _playwright_dispatch(page, _SEL["btn_apply_exact"])),
                ("dispatch_event(btn)",     lambda: _playwright_dispatch(page, _SEL["btn_apply_nosuffix"])),
                ("dispatchEvent JS(btn)",   lambda: _dispatch_event_click(page, _BTN_ID)),
                ("dispatchEvent JS(icon)",  lambda: _dispatch_event_click(page, _ICON_ID)),
                ("XPath force(icontext)",   lambda: _click_force(page, _SEL["btn_apply_exact"])),
                ("XPath force(nosuffix)",   lambda: _click_force(page, _SEL["btn_apply_nosuffix"])),
                ("XPath 모든 프레임",       lambda: _click_any_frame(page, _SEL["btn_apply_exact"])),
                ("ID 부분일치",             lambda: _click_any_frame(page, _SEL["btn_apply_contains"])),
                ("JS getElementById",       lambda: _js_click(page, [_ICON_ID, _BTN_ID])),
            ]
            clicked = False
            for label, attempt in apply_attempts:
                try:
                    result = await attempt()
                    if result:
                        logger.info(f"[Qings] Apply 클릭 성공 ({label})")
                        clicked = True
                        break
                except Exception:
                    pass
                logger.warning(f"[Qings] Apply 실패: {label}")

            if not clicked:
                logger.error("[Qings] ── Apply 버튼 진단 시작 ──")
                for frame in page.frames:
                    try:
                        hits = await frame.evaluate("""
                            () => {
                                const results = [];
                                // 1) 텍스트에 Apply/적용 포함된 요소
                                document.querySelectorAll('*').forEach(el => {
                                    const txt = (el.innerText || el.textContent || '').trim();
                                    if (txt && (txt.includes('Apply') || txt.includes('적용')) && txt.length < 30) {
                                        results.push({reason:'text', id: el.id||'(no-id)', tag: el.tagName, text: txt});
                                    }
                                });
                                // 2) INPUT / BUTTON 요소 전부
                                document.querySelectorAll('input, button').forEach(el => {
                                    results.push({reason:'tag', id: el.id||'(no-id)', tag: el.tagName,
                                        text: (el.value||el.innerText||'').trim().slice(0,30)});
                                });
                                // 3) onclick 속성 가진 요소
                                document.querySelectorAll('[onclick]').forEach(el => {
                                    results.push({reason:'onclick', id: el.id||'(no-id)', tag: el.tagName,
                                        text: (el.innerText||'').trim().slice(0,30)});
                                });
                                return results.slice(0, 30);
                            }
                        """)
                        if hits:
                            logger.error(f"  [frame={frame.name or 'main'}]")
                            for h in hits:
                                logger.error(f"    [{h['reason']}] <{h['tag']}> id={h['id']!r} text={h['text']!r}")
                    except Exception as e:
                        logger.error(f"  [frame={frame.name or 'main'}] 진단 오류: {e}")
                logger.error("[Qings] ── 진단 끝 ──")
                raise RuntimeError("Apply 버튼을 찾지 못했습니다. 위 진단 결과를 확인하세요.")

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


async def _nexacro_click(page: Page, component_path: str) -> bool:
    """Nexacro 컴포넌트 JS API .click() — 표준 DOM click과 달리 Nexacro 이벤트를 발생시킵니다."""
    script = (
        "() => { try {"
        f" const nc = {component_path};"
        " if (nc && typeof nc.click === 'function') { nc.click(); return true; }"
        " } catch(e) {} return false; }"
    )
    for frame in page.frames:
        try:
            result = await frame.evaluate(script)
            if result:
                logger.info(f"[Qings] Nexacro .click() 성공 (frame: {frame.name or frame.url[:40]})")
                return True
        except Exception:
            continue
    return False


async def _nexacro_fire_event(page: Page, component_path: str) -> bool:
    """Nexacro fireEvent('onclick') — 컴포넌트 이벤트 핸들러를 직접 발동합니다."""
    script = (
        "() => { try {"
        f" const nc = {component_path};"
        " if (nc && typeof nc.fireEvent === 'function') { nc.fireEvent('onclick', null, null); return true; }"
        " } catch(e) {} return false; }"
    )
    for frame in page.frames:
        try:
            result = await frame.evaluate(script)
            if result:
                logger.info(f"[Qings] Nexacro fireEvent 성공 (frame: {frame.name or frame.url[:40]})")
                return True
        except Exception:
            continue
    return False


async def _click_force(page: Page, xpath: str, timeout: int = 5_000) -> bool:
    """force=True 클릭 — tabindex=-1 등 interactable 검사를 우회합니다."""
    for frame in page.frames:
        try:
            loc = frame.locator(f"xpath={xpath}")
            if await loc.count() > 0:
                await loc.first.click(timeout=timeout, force=True)
                logger.info(f"[Qings] force 클릭 성공 (frame: {frame.name or frame.url[:40]})")
                return True
        except Exception:
            continue
    return False


async def _playwright_dispatch(page: Page, xpath: str, timeout: int = 5_000) -> bool:
    """Playwright dispatch_event('click') — force 없이 이벤트를 직접 발송합니다."""
    for frame in page.frames:
        try:
            loc = frame.locator(f"xpath={xpath}")
            if await loc.count() > 0:
                await loc.first.dispatch_event("click", timeout=timeout)
                logger.info(f"[Qings] dispatch_event 성공 (frame: {frame.name or frame.url[:40]})")
                return True
        except Exception:
            continue
    return False


async def _dispatch_event_click(page: Page, element_id: str) -> bool:
    """JS로 mousedown+mouseup+click 이벤트를 순서대로 발생시킵니다."""
    script = (
        f"() => {{ const el = document.getElementById({repr(element_id)});"
        " if (!el) return false;"
        " const r = el.getBoundingClientRect();"
        " const cx = r.left + r.width/2, cy = r.top + r.height/2;"
        " ['mousedown','mouseup','click'].forEach(t => {"
        "   el.dispatchEvent(new MouseEvent(t, {bubbles:true,cancelable:true,clientX:cx,clientY:cy}));"
        " }); return true; }"
    )
    for frame in page.frames:
        try:
            result = await frame.evaluate(script)
            if result:
                logger.info(f"[Qings] JS dispatchEvent 성공: {element_id}")
                return True
        except Exception:
            continue
    return False


async def _mouse_position_click(page: Page, element_id: str) -> bool:
    """요소의 화면 좌표를 구해 실제 마우스로 클릭합니다 — tabindex/visibility 우회."""
    for frame in page.frames:
        try:
            pos = await frame.evaluate(
                f"() => {{ const el = document.getElementById({repr(element_id)});"
                " if (!el) return null;"
                " const r = el.getBoundingClientRect();"
                " if (r.width===0||r.height===0) return null;"
                " return {x: r.left+r.width/2, y: r.top+r.height/2}; }}"
            )
            if not pos:
                continue
            x, y = pos["x"], pos["y"]
            # iframe이면 프레임 오프셋 추가
            if frame != page.main_frame:
                try:
                    fb = await (await frame.frame_element()).bounding_box()
                    if fb:
                        x += fb["x"]
                        y += fb["y"]
                except Exception:
                    pass
            await page.mouse.move(x, y)
            await asyncio.sleep(0.1)
            await page.mouse.click(x, y)
            logger.info(f"[Qings] 좌표 클릭 성공: {element_id} @ ({x:.0f},{y:.0f})")
            return True
        except Exception:
            continue
    return False


async def _close_filter_panel(page: Page):
    """돋보기 필터 패널을 닫습니다 — btn_search(패널 내 적용 버튼) 클릭 시도."""
    sel = _SEL["btn_filter_search"]
    for frame in page.frames:
        try:
            loc = frame.locator(f"xpath={sel}")
            if await loc.count() > 0:
                await loc.first.click(timeout=3_000)
                logger.info("[Qings] 필터 패널 닫기 완료 (btn_filter_search)")
                await asyncio.sleep(0.8)
                return
        except Exception:
            continue
    logger.debug("[Qings] 필터 패널 닫기 버튼 없음 (이미 닫혔거나 불필요)")


async def _fill_date(page: Page, xpath: str, date_str: str):
    """날짜 입력 필드를 채웁니다."""
    loc = page.locator(f"xpath={xpath}")
    await loc.click()
    await loc.fill("")
    await loc.type(date_str, delay=50)
    await page.keyboard.press("Tab")
    await asyncio.sleep(0.3)
