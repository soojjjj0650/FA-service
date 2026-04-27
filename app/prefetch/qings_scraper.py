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

    # 필터 패널 내 검색/적용 버튼
    "btn_filter_search": '//*[@id="mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001'
                         '.form.div_left.form.div_FormFilter.form.btn_search:icontext"]',

    # Apply 버튼 — id 속성이 없으므로 class 속성으로 탐색 (btn_WFSA_Apply)
    "btn_apply_class":    '//*[contains(@class,"btn_WFSA_Apply")]',
    "btn_apply_exact":    '//*[@id="mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001.form.div_left.form.btn_Apply:icontext"]',
    "btn_apply_nosuffix": '//*[@id="mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001.form.div_left.form.btn_Apply"]',
    "btn_apply_contains": 'xpath=//*[contains(@id,"btn_Apply")]',
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

            # ── 6.5 팝업 닫기 (Escape만 — date_from 클릭하면 달력이 열려 Apply를 가림)
            for _ in range(3):
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
            await asyncio.sleep(0.5)

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

            # 페이지 포커스 확보 및 스크린샷
            await page.bring_to_front()
            await asyncio.sleep(0.3)
            try:
                await page.screenshot(path="/tmp/qings_before_apply.png")
                logger.info("[Qings] 스크린샷 저장: /tmp/qings_before_apply.png")
            except Exception:
                pass

            # Apply 버튼 좌표 사전 진단 — 해당 좌표에 실제로 뭐가 있는지 확인
            for frame in page.frames:
                try:
                    loc = frame.locator(f"xpath={_SEL['btn_apply_class']}")
                    if await loc.count() == 0:
                        continue
                    bb = await loc.first.bounding_box()
                    logger.info(f"[Qings] Apply bounding_box={bb} frame={frame.url[:60]}")
                    if bb and bb["width"] > 0:
                        cx, cy = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
                        top_el = await frame.evaluate(
                            f"() => {{ const el = document.elementFromPoint({cx},{cy});"
                            " return el ? {tag:el.tagName,cls:el.className.slice(0,60),id:(el.id||'').slice(0,60)} : null; }"
                        )
                        logger.info(f"[Qings] elementFromPoint({cx:.0f},{cy:.0f}): {top_el}")
                except Exception as _e:
                    logger.info(f"[Qings] Apply 진단 오류: {_e}")

            # Apply 버튼 클릭 시도
            # 1순위: Nexacro 컴포넌트 직접 접근 (class 셀렉터 → _component → onclick 호출)
            apply_attempts = [
                ("Nexacro 컴포넌트(class)",  lambda: _nexacro_click(page, _NX)),
                ("class 좌표클릭",           lambda: _mouse_position_click_xpath(page, _SEL["btn_apply_class"])),
                ("class 클릭(no force)",     lambda: _click_any_frame(page, _SEL["btn_apply_class"])),
                ("focus+Enter(class)",       lambda: _focus_and_enter_xpath(page, _SEL["btn_apply_class"])),
                ("class 클릭(force)",        lambda: _click_force(page, _SEL["btn_apply_class"])),
                ("XPath force(icontext)",    lambda: _click_force(page, _SEL["btn_apply_exact"])),
                ("XPath force(nosuffix)",    lambda: _click_force(page, _SEL["btn_apply_nosuffix"])),
                ("XPath 모든 프레임",        lambda: _click_any_frame(page, _SEL["btn_apply_exact"])),
                ("JS coords dispatch",       lambda: _dispatch_apply_js(page)),
            ]
            clicked = False
            for label, attempt in apply_attempts:
                try:
                    result = await attempt()
                    if result:
                        logger.info(f"[Qings] Apply 클릭 성공 ({label})")
                        clicked = True
                        break
                except Exception as _ex:
                    logger.warning(f"[Qings] Apply 예외 ({label}): {_ex}")
                logger.warning(f"[Qings] Apply 실패: {label}")

            # 클릭 직후 스크린샷
            try:
                await page.screenshot(path="/tmp/qings_after_apply.png")
                logger.info("[Qings] 클릭 후 스크린샷: /tmp/qings_after_apply.png")
            except Exception:
                pass

            if not clicked:
                logger.error("[Qings] ── Apply 버튼 진단 시작 ──")
                for frame in page.frames:
                    try:
                        hits = await frame.evaluate("""
                            () => {
                                const results = [];
                                const BTN_ID = 'mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001.form.div_left.form.btn_Apply';
                                // 1) btn_Apply 위치에 실제로 있는 요소 (overlay 탐지)
                                const btn = document.getElementById(BTN_ID);
                                if (btn) {
                                    const r = btn.getBoundingClientRect();
                                    const cx = r.left + r.width/2, cy = r.top + r.height/2;
                                    const top = document.elementFromPoint(cx, cy);
                                    results.push({reason:'elementFromPoint',
                                        id: top ? (top.id||'(no-id)') : 'null',
                                        tag: top ? top.tagName : 'null',
                                        text: top ? (top.innerText||'').trim().slice(0,40) : '',
                                        rect: JSON.stringify({x:Math.round(cx),y:Math.round(cy),w:Math.round(r.width),h:Math.round(r.height)})
                                    });
                                }
                                // 2) 텍스트에 Apply/적용 포함된 요소
                                document.querySelectorAll('*').forEach(el => {
                                    const txt = (el.innerText || el.textContent || '').trim();
                                    if (txt && (txt.includes('Apply') || txt.includes('적용')) && txt.length < 30) {
                                        const r2 = el.getBoundingClientRect();
                                        results.push({reason:'text', id: el.id||'(no-id)', tag: el.tagName, text: txt,
                                            rect: JSON.stringify({x:Math.round(r2.left),y:Math.round(r2.top),w:Math.round(r2.width),h:Math.round(r2.height)})});
                                    }
                                });
                                return results.slice(0, 20);
                            }
                        """)
                        if hits:
                            logger.error(f"  [frame={frame.name or 'main'}]")
                            for h in hits:
                                logger.error(f"    [{h['reason']}] <{h['tag']}> id={h['id']!r} text={h.get('text','')!r} rect={h.get('rect','')}")
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
    """Nexacro 컴포넌트의 onclick 핸들러를 직접 호출합니다.

    F12 콘솔 기본값은 top 프레임 — 거기서 window.mainframe = qings iframe window.
    따라서 page.evaluate()(= top 프레임)에서 직접 경로를 실행하고,
    실패 시 각 자식 프레임에서 window.parent 경유로 시도합니다.
    """
    dot = component_path.rfind(".")
    comp_id = component_path[dot + 1:]   # btn_Apply
    handler = comp_id + "_onclick"
    full_path = component_path  # mainframe...form.div_left.form.btn_Apply

    _SUCCESS = frozenset(['form_handler', 'doClick', 'click',
                          'top_form_handler', 'top_doClick', 'top_click',
                          'par_form_handler', 'par_doClick', 'par_click',
                          'dom_mouseevt'])
    # _is_success: found_no_method는 진단값이지 성공이 아님
    def _is_success(r: str) -> bool:
        return r in _SUCCESS or any(r.startswith(p) for p in [
            'dom_form_handler:', 'dom_doClick:', 'fireEvent:',
            'ctrl_doClick', 'ctrl_fireEvent', 'ctrl_parent_handler',
            'linked_parent_handler', 'parentElm_doClick', 'parentElm_fireEvent',
            'par_btn_doClick', 'par_btn_fireEvent', 'par_btn_parent_handler',
            'refform_handler', 'all_doClick', 'all_fireEvent',
            'rf_all_doClick', 'rf_all_fireEvent', 'rf_all_parent_handler',
            'rf_btn_doClick', 'rf_btn_fireEvent', 'rf_proto_handler',
            'all_getObject_doClick', 'all_getObject_fireEvent',
            'all_findById_doClick', 'all_find_doClick', 'all_item_doClick',
        ])

    def _make_script(prefix: str, path_expr: str) -> str:
        """path_expr 로 컴포넌트에 접근해 핸들러를 호출하는 JS 반환."""
        return f"""
        () => {{
            function tryCall(form_dl, comp) {{
                if (!form_dl || !comp) return null;
                if (typeof form_dl[{repr(handler)}] === 'function') {{
                    form_dl[{repr(handler)}].call(form_dl, comp, null);
                    return {repr(prefix + 'form_handler')};
                }}
                if (typeof comp.doClick === 'function') {{ comp.doClick(); return {repr(prefix + 'doClick')}; }}
                if (comp.click) {{ comp.click(); return {repr(prefix + 'click')}; }}
                return null;
            }}
            try {{
                const form_dl = {path_expr};
                const comp = form_dl && form_dl[{repr(comp_id)}];
                return tryCall(form_dl, comp) || 'no_method';
            }} catch(e) {{ return 'err:' + e.message.slice(0,80); }}
        }}
        """

    # ── 1. top 프레임에서 직접 경로 (F12 콘솔과 동일한 컨텍스트) ────────
    top_form = "mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001.form.div_left.form"
    try:
        result = await page.evaluate(_make_script('top_', top_form))
        logger.warning(f"[Qings] top 프레임 결과: {result!r}")
        if result in _SUCCESS:
            logger.info(f"[Qings] Nexacro 핸들러 성공 (top): {result}")
            return True
    except Exception as e:
        logger.warning(f"[Qings] top 프레임 오류: {e}")

    # ── 2. 각 자식 프레임에서 window.parent 경유 ────────────────────────
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            result = await frame.evaluate(_make_script('par_', "window.parent." + top_form))
            if result in _SUCCESS:
                logger.info(f"[Qings] Nexacro 핸들러 성공 (parent): {result} frame={frame.url[:50]}")
                return True
            elif result and not result.startswith('no_method') and not result.startswith('err:SecurityError'):
                logger.warning(f"[Qings] parent 경유 결과: {result!r} frame={frame.url[:50]}")
        except Exception:
            continue

    # ── 3. class 셀렉터 → _linked_element.linkedcontrol.parent 파고들기 ───
    dom_script = f"""
    () => {{
        const el = document.querySelector('[class*="btn_WFSA_Apply"]');
        if (!el) return 'no_el';
        const linked = el._linked_element;
        if (!linked) return 'no_linked';
        const ctrl = linked.linkedcontrol;
        if (!ctrl) return 'no_ctrl';
        const par = ctrl.parent;
        if (!par) return 'no_par';

        const H = {repr(handler)};

        // ① par['btn_Apply'] — Nexacro 폼에서 자식 컴포넌트 직접 접근
        const btn = par['btn_Apply'];
        if (btn) {{
            if (typeof btn.doClick === 'function') {{ btn.doClick(); return 'par_btn_doClick'; }}
            if (typeof btn.fireEvent === 'function') {{ btn.fireEvent('onclick', null, null); return 'par_btn_fireEvent'; }}
            const bp = btn.parent;
            if (bp && typeof bp[H] === 'function') {{ bp[H].call(bp, btn, null); return 'par_btn_parent_handler'; }}
            return 'par_btn_keys:' + Object.keys(btn).slice(0,15).join(',');
        }}

        // ② par._refform — 이벤트 핸들러가 있는 참조 폼
        const rf = par._refform || ctrl._reform;
        if (rf) {{
            if (typeof rf[H] === 'function') {{ rf[H].call(par, ctrl, null); return 'refform_handler'; }}

            // rf.all['btn_Apply'] — Nexacro form.all 컬렉션
            const all = rf.all;
            if (all) {{
                const btn = all['btn_Apply'] || all.btn_Apply;
                if (btn) {{
                    if (typeof btn.doClick === 'function') {{ btn.doClick(); return 'rf_all_doClick'; }}
                    if (typeof btn.fireEvent === 'function') {{ btn.fireEvent('onclick', null, null); return 'rf_all_fireEvent'; }}
                    const bp = btn.parent;
                    if (bp && typeof bp[H] === 'function') {{ bp[H].call(bp, btn, null); return 'rf_all_parent_handler'; }}
                    return 'rf_all_btn_keys:' + Object.keys(btn).slice(0,15).join(',');
                }}
            }}

            // rf['btn_Apply'] 직접 접근
            const rfBtn = rf['btn_Apply'];
            if (rfBtn) {{
                if (typeof rfBtn.doClick === 'function') {{ rfBtn.doClick(); return 'rf_btn_doClick'; }}
                if (typeof rfBtn.fireEvent === 'function') {{ rfBtn.fireEvent('onclick', null, null); return 'rf_btn_fireEvent'; }}
                return 'rf_btn_keys:' + Object.keys(rfBtn).slice(0,15).join(',');
            }}

            // rf 프로토타입 체인에서 btn_Apply_onclick 탐색
            for (let obj = rf; obj; obj = Object.getPrototypeOf(obj)) {{
                if (typeof obj[H] === 'function') {{ obj[H].call(rf, ctrl, null); return 'rf_proto_handler'; }}
            }}

            // rf.all — Nexacro ComponentCollection 접근 방법 탐색
            if (all) {{
                // getObject 메서드 시도 (Nexacro NexaComponentListObject)
                const methods = ['getObject','findById','find','item'].filter(m => typeof all[m] === 'function');
                for (const m of methods) {{
                    const btn = all[m]('btn_Apply');
                    if (btn) {{
                        if (typeof btn.doClick === 'function') {{ btn.doClick(); return 'all_' + m + '_doClick'; }}
                        if (typeof btn.fireEvent === 'function') {{ btn.fireEvent('onclick', null, null); return 'all_' + m + '_fireEvent'; }}
                        return 'all_' + m + '_btn_keys:' + Object.keys(btn).slice(0,15).join(',');
                    }}
                }}
                return 'rf_all_debug:type=' + (all.constructor ? all.constructor.name : typeof all) + ',methods=' + methods.join(',') + ',len=' + (all.length||'?');
            }}

            // ctrl.parent와 rf에서 for..in으로 Apply/btn_ 함수 찾기
            const parFns = [], rfFns = [];
            for (const k in par) {{ if (typeof par[k]==='function') parFns.push(k); }}
            for (const k in rf)  {{ if (typeof rf[k]==='function')  rfFns.push(k); }}
            const parApply = parFns.filter(k => /apply|btn_|onclick/i.test(k));
            const rfApply  = rfFns.filter(k => /apply|btn_|onclick/i.test(k));
            if (parApply.length) return 'par_forin_apply:' + parApply.join(',');
            if (rfApply.length)  return 'rf_forin_apply:'  + rfApply.join(',');

            return 'rf_exhausted:par_id=' + par.id + ',par_fns=' + parFns.length + ',rf_fns=' + rfFns.length;
        }}

        // ③ ctrl.parent의 프로토타입 체인에서 Apply 관련 핸들러 검색
        for (let obj = par; obj; obj = Object.getPrototypeOf(obj)) {{
            const ns = Object.getOwnPropertyNames(obj);
            const applyKeys = ns.filter(k => k.toLowerCase().includes('apply'));
            if (applyKeys.length) return 'proto_apply:' + applyKeys.join(',');
        }}

        // ④ par.all 컬렉션
        const all = par.all;
        if (all && all['btn_Apply']) {{
            const ab = all['btn_Apply'];
            if (typeof ab.doClick === 'function') {{ ab.doClick(); return 'all_doClick'; }}
            if (typeof ab.fireEvent === 'function') {{ ab.fireEvent('onclick', null, null); return 'all_fireEvent'; }}
            return 'all_btn_keys:' + Object.keys(ab).slice(0,15).join(',');
        }}

        return 'exhausted:par_id=' + par.id + ',btn_Apply=' + typeof par['btn_Apply'] + ',rf=' + typeof (par._refform||ctrl._reform);
    }}
    """
    for frame in page.frames:
        try:
            result = await frame.evaluate(dom_script)
            logger.warning(f"[Qings] DOM(class) 결과: {result!r} frame={frame.url[:50]}")
            if result in _SUCCESS or _is_success(result):
                logger.info(f"[Qings] DOM(class) 성공: {result}")
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


async def _mouse_position_click_xpath(page: Page, xpath: str, timeout: int = 5_000) -> bool:
    """XPath로 요소를 찾아 좌표를 구한 뒤 page.mouse.click()으로 클릭합니다.

    Playwright bounding_box()는 이미 main frame viewport 기준 좌표를 반환하므로
    iframe offset을 추가하면 이중 계산이 됩니다. offset 보정 없이 사용합니다.
    page.mouse.click()은 isTrusted=true 이벤트를 발생시켜 Nexacro가 처리합니다.
    """
    for frame in page.frames:
        try:
            loc = frame.locator(f"xpath={xpath}")
            if await loc.count() == 0:
                continue
            bb = await loc.first.bounding_box()
            if not bb or bb["width"] == 0 or bb["height"] == 0:
                logger.warning(f"[Qings] 좌표클릭: bounding_box 없음 (frame={frame.url[:50]})")
                continue
            # bounding_box()는 viewport 기준 좌표 — iframe offset 추가 불필요
            x = bb["x"] + bb["width"] / 2
            y = bb["y"] + bb["height"] / 2
            logger.info(f"[Qings] XPath 좌표클릭 시도: ({x:.0f},{y:.0f}) frame={frame.url[:50]}")
            await page.mouse.move(x, y)
            await asyncio.sleep(0.15)
            await page.mouse.click(x, y)
            logger.info(f"[Qings] XPath 좌표클릭 완료: ({x:.0f},{y:.0f})")
            return True
        except Exception as e:
            logger.warning(f"[Qings] 좌표클릭 예외: {e}")
            continue
    return False


async def _focus_and_enter_xpath(page: Page, xpath: str) -> bool:
    """XPath로 요소를 찾아 focus() 후 Enter를 보냅니다."""
    for frame in page.frames:
        try:
            loc = frame.locator(f"xpath={xpath}")
            if await loc.count() == 0:
                continue
            await loc.first.focus()
            await asyncio.sleep(0.2)
            await page.keyboard.press("Return")
            logger.info(f"[Qings] XPath focus+Enter 성공")
            return True
        except Exception:
            continue
    return False


async def _focus_and_enter(page: Page, element_id: str) -> bool:
    """el.focus() 후 Enter/Space 키 전송 — tabindex=-1 버튼도 키보드로 활성화."""
    for frame in page.frames:
        try:
            exists = await frame.evaluate(
                f"() => {{ const el = document.getElementById({repr(element_id)});"
                " if (!el) return false; el.focus(); return true; }}"
            )
            if exists:
                await asyncio.sleep(0.2)
                await page.keyboard.press("Return")
                await asyncio.sleep(0.1)
                logger.info(f"[Qings] focus+Enter 시도: {element_id}")
                return True
        except Exception:
            continue
    return False


async def _close_filter_panel(page: Page):
    """돋보기 필터 패널을 닫습니다.
    1순위: Nexacro 폼 핸들러로 btn_search 클릭
    2순위: 날짜 필드 클릭으로 포커스 이동 → 패널 자동 닫힘
    """
    _SEARCH_PATH = ("mainframe.VFrameSet0.WorkFrame.WORK_FRAME_QUA1001"
                    ".form.div_left.form.div_FormFilter.form.btn_search")

    # 1) Nexacro 폼 핸들러로 btn_search 실행
    try:
        ok = await _nexacro_click(page, _SEARCH_PATH)
        if ok:
            logger.info("[Qings] 필터 패널 닫기: Nexacro 핸들러 성공")
            await asyncio.sleep(0.8)
            return
    except Exception:
        pass

    # 2) 날짜 필드 클릭으로 포커스 이동 (Nexacro dropdown은 외부 클릭 시 자동 닫힘)
    try:
        await _click(page, _SEL["date_from"])
        logger.info("[Qings] 필터 패널 닫기: 날짜 필드 클릭으로 포커스 이동")
        await asyncio.sleep(0.5)
        return
    except Exception:
        pass

    logger.debug("[Qings] 필터 패널 닫기 실패 — 계속 진행")


async def _dispatch_apply_js(page: Page) -> bool:
    """Apply 버튼에 JS로 올바른 좌표의 마우스 이벤트를 dispatch합니다.

    el에 직접 dispatch → target=el, bubbles=true로 document까지 전파.
    clientX/clientY = getBoundingClientRect 기준이므로 Nexacro 좌표 라우팅에 부합.
    """
    script = """
    () => {
        const el = document.querySelector('[class*="btn_WFSA_Apply"]');
        if (!el) return 'no_el';
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) return 'zero:' + JSON.stringify({x:Math.round(r.left),y:Math.round(r.top),w:Math.round(r.width),h:Math.round(r.height)});
        const cx = r.left + r.width / 2;
        const cy = r.top + r.height / 2;
        const base = {bubbles:true, cancelable:true, view:window, clientX:cx, clientY:cy, screenX:cx, screenY:cy};
        el.dispatchEvent(new MouseEvent('mouseover',  base));
        el.dispatchEvent(new MouseEvent('mousemove',  base));
        el.dispatchEvent(new MouseEvent('mouseenter', {bubbles:false, cancelable:true, view:window, clientX:cx, clientY:cy}));
        el.dispatchEvent(new MouseEvent('mousedown',  Object.assign({button:0, buttons:1}, base)));
        el.dispatchEvent(new MouseEvent('mouseup',    Object.assign({button:0, buttons:0}, base)));
        el.dispatchEvent(new MouseEvent('click',      Object.assign({button:0, buttons:0}, base)));
        return 'ok:' + Math.round(cx) + ',' + Math.round(cy);
    }
    """
    for frame in page.frames:
        try:
            result = await frame.evaluate(script)
            logger.info(f"[Qings] JS dispatch 결과: {result!r} frame={frame.url[:60]}")
            if isinstance(result, str) and result.startswith("ok:"):
                return True
        except Exception as e:
            logger.debug(f"[Qings] JS dispatch 오류: {e}")
    return False


async def _fill_date(page: Page, xpath: str, date_str: str):
    """날짜 입력 필드를 채웁니다."""
    loc = page.locator(f"xpath={xpath}")
    await loc.click()
    await loc.fill("")
    await loc.type(date_str, delay=50)
    await page.keyboard.press("Tab")
    await asyncio.sleep(0.3)
