"""
Samsung.net 메일 다운로더

동작 흐름:
  1. www.samsung.net 로그인 (ID/PW)
  2. 메일 버튼 클릭  →  button[aria-label="메일"]
  3. FA 미결건 폴더 클릭  →  button > span.text("FA 미결건")
  4. 메일 목록 스크롤하며 각 메일 제목 클릭  →  div.inner-cell.col03-01 a
  5. 첨부파일 체크박스 전체 선택  →  label:has(i.check.md)
  6. 저장 버튼 클릭  →  button[aria-label="저장"]
  7. 다운로드 파일을 FAdata 폴더에 저장
  8. 처리한 메일 제목을 downloaded_ids 에 기록 (중복 방지)
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Page, BrowserContext, Download

from app.config import settings

logger = logging.getLogger(__name__)

_AUTH_STATE_PATH   = Path("data") / "sessions" / "mail_auth_state.json"
_DOWNLOADED_IDS_FILE = Path("data") / "sessions" / "mail_downloaded_ids.json"

_EXCEL_EXTS = {".xlsx", ".xls", ".xlsm"}

# ─── 셀렉터 ───────────────────────────────────────────────────────────────────
_SEL_MAIL_BTN    = 'button[aria-label="메일"]'
_SEL_FOLDER      = 'button:has(span.text:text("FA 미결건"))'
_SEL_MAIL_ROW    = '#DEFAULT_scroll-list > div > div:nth-child(2) > div'
_SEL_MAIL_CHK    = 'span[role="check"][aria-label="선택"]'
_SEL_SCROLL_CTR  = '#DEFAULT_scroll-list'
_SEL_SAVE_ALL    = 'button[aria-label="모두저장"]'   # 새 창에서 클릭할 버튼


def _save_dir() -> str:
    d = settings.MAIL_SAVE_DIR or os.path.join(settings.CSV_DOWNLOAD_PATH, "FAdata")
    os.makedirs(d, exist_ok=True)
    return d


def _load_ids() -> set:
    try:
        if _DOWNLOADED_IDS_FILE.exists():
            return set(json.loads(_DOWNLOADED_IDS_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    return set()


def _save_ids(ids: set) -> None:
    _DOWNLOADED_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _DOWNLOADED_IDS_FILE.write_text(
        json.dumps(list(ids), ensure_ascii=False), encoding="utf-8"
    )


# ─── 메인 함수 ────────────────────────────────────────────────────────────────

async def download_mail_attachments() -> list[str]:
    """FA 미결건 폴더 신규 메일의 Excel 첨부파일을 다운로드합니다."""
    save_dir   = _save_dir()
    done_ids   = _load_ids()
    saved: list[str] = []

    _AUTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    pw = await async_playwright().start()
    try:
        launch_kw: dict = {
            "headless": settings.MAIL_HEADLESS,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--start-maximized",
            ],
        }
        if settings.EDGE_EXECUTABLE_PATH and os.path.exists(settings.EDGE_EXECUTABLE_PATH):
            launch_kw["executable_path"] = settings.EDGE_EXECUTABLE_PATH

        browser = await pw.chromium.launch(**launch_kw)
        ctx_kw: dict = {
            "accept_downloads": True,
            "viewport": None,
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
            ),
        }
        if _AUTH_STATE_PATH.exists():
            ctx_kw["storage_state"] = str(_AUTH_STATE_PATH)

        context = await browser.new_context(**ctx_kw)
        page    = await context.new_page()

        try:
            await _login(page, context)
            await _go_to_mail(page)
            await _open_folder(page)
            saved = await _process_mail_list(page, context, save_dir, done_ids)
            _save_ids(done_ids)
            logger.info(f"[Mail] 완료 — {len(saved)}개 파일 저장")
        finally:
            await context.close()
            await browser.close()
    finally:
        await pw.stop()

    return saved


# ─── 단계별 함수 ──────────────────────────────────────────────────────────────

async def _login(page: Page, context: BrowserContext) -> None:
    """www.samsung.net 로그인"""
    logger.info("[Mail] samsung.net 접속...")
    await page.goto(settings.MAIL_URL, wait_until="domcontentloaded", timeout=30_000)
    await asyncio.sleep(2)

    pw_loc = page.locator(".login-pw input, input[type='password']")
    if await pw_loc.count() > 0:
        id_loc = page.locator(".login-id input, input[type='text'], input[name='userId']")
        if await id_loc.count() > 0:
            await id_loc.first.triple_click()
            await id_loc.first.type(settings.MAIL_USERNAME, delay=50)
        await pw_loc.first.triple_click()
        await pw_loc.first.type(settings.MAIL_PASSWORD, delay=50)
        await pw_loc.first.press("Enter")
        await asyncio.sleep(4)
        logger.info("[Mail] 로그인 완료")
    else:
        logger.info("[Mail] 이미 로그인됨")

    await context.storage_state(path=str(_AUTH_STATE_PATH))


async def _go_to_mail(page: Page) -> None:
    """메인 화면에서 메일 버튼 클릭"""
    logger.info(f"[Mail] 메일 버튼 클릭... (현재 URL: {page.url})")
    mail_btn = page.locator(_SEL_MAIL_BTN).first
    await mail_btn.wait_for(state="visible", timeout=15_000)
    await mail_btn.click()
    await asyncio.sleep(3)
    logger.info(f"[Mail] 메일 화면 진입 (현재 URL: {page.url})")


async def _open_folder(page: Page) -> None:
    """FA 미결건 폴더 클릭"""
    folder_name = settings.MAIL_FOLDER_NAME
    logger.info(f"[Mail] '{folder_name}' 폴더 클릭... (프레임 수: {len(page.frames)})")

    selectors = [
        f'button:has(span.text:text("{folder_name}"))',
        f'button:has(span:text("{folder_name}"))',
        f'button:has-text("{folder_name}")',
        f':text("{folder_name}")',
    ]

    for ctx in [page, *page.frames]:
        frame_url = getattr(ctx, 'url', 'main')
        for sel in selectors:
            try:
                btn = ctx.locator(sel).first
                if await btn.is_visible(timeout=2_000):
                    logger.info(f"[Mail] 폴더 버튼 발견 (frame={frame_url}, sel={sel})")
                    await btn.click()
                    await asyncio.sleep(4)
                    logger.info(f"[Mail] '{folder_name}' 폴더 열림")
                    return
            except Exception:
                continue

    logger.warning(f"[Mail] '{folder_name}' 폴더를 찾지 못했습니다 — 프레임 URL 목록:")
    for f in [page, *page.frames]:
        logger.warning(f"  frame: {getattr(f, 'url', 'main')}")


async def _find_frame_with(page: Page, selector: str):
    """selector가 존재하는 프레임을 반환 (page 포함)"""
    for ctx in [page, *page.frames]:
        try:
            if await ctx.locator(selector).count() > 0:
                return ctx
        except Exception:
            continue
    return page


async def _process_mail_list(
    page: Page,
    context: BrowserContext,
    save_dir: str,
    done_ids: set,
) -> list[str]:
    """메일 목록을 스크롤하며 신규 메일 처리"""
    saved: list[str] = []
    processed_this_run: list[str] = []

    # 메일 목록 로드 대기 (최대 20초 재시도)
    chk_frame, checkboxes, count = page, page.locator(_SEL_MAIL_CHK), 0
    for attempt in range(10):
        chk_frame, checkboxes, count = await _find_checkboxes(page)
        logger.info(f"[Mail] 체크박스 탐색 {attempt+1}회: {count}개 발견")
        if count > 0:
            break
        await asyncio.sleep(2)

    if count == 0:
        logger.warning("[Mail] 메일 목록을 찾지 못했습니다 (체크박스 없음) — 프레임 목록:")
        for f in [page, *page.frames]:
            logger.warning(f"  frame: {getattr(f, 'url', 'main')}")
        return saved

    for i in range(count):
        try:
            chk = checkboxes.nth(i)
            # #DEFAULT_scroll-list 안에서 해당 체크박스가 속한 행의 제목 추출
            subject = await chk.evaluate("""el => {
                const container = document.getElementById('DEFAULT_scroll-list');
                if (container) {
                    const rows = container.querySelectorAll(':scope > div > div:nth-child(2) > div');
                    for (const row of rows) {
                        if (row.contains(el)) {
                            const cell = row.querySelector('div > div:first-child');
                            const t = (cell || row).innerText?.trim()?.split('\\n')[0] || '';
                            if (t) return t;
                        }
                    }
                }
                return el.closest('li, tr, [class*="row"], [class*="item"]')
                         ?.innerText?.split('\\n')[0]?.trim() || '';
            }""") or f"mail_{i}"

            if subject in done_ids or subject in processed_this_run:
                logger.info(f"[Mail] [{i+1}] '{subject}' 이미 처리됨 — 건너뜀")
                continue

            logger.info(f"[Mail] [{i+1}/{count}] '{subject}' 처리 중...")
            files = await _open_and_download(page, chk_frame, chk, i, save_dir)

            if files:
                saved.extend(files)
                logger.info(f"[Mail] 저장: {files}")
            done_ids.add(subject)
            processed_this_run.append(subject)

            await asyncio.sleep(1)

        except Exception as e:
            logger.warning(f"[Mail] {i+1}번 메일 처리 오류: {e}")
            continue

    return saved


async def _find_checkboxes(page: Page):
    """모든 프레임에서 체크박스를 찾아 (frame, locator, count) 반환"""
    for ctx in [page, *page.frames]:
        try:
            loc = ctx.locator(_SEL_MAIL_CHK)
            cnt = await loc.count()
            if cnt > 0:
                logger.info(f"[Mail] 체크박스 {cnt}개 (프레임: {getattr(ctx, 'url', 'main')})")
                return ctx, loc, cnt
        except Exception:
            continue
    return page, page.locator(_SEL_MAIL_CHK), 0


async def _find_scroll_frame(page: Page):
    """모든 프레임에서 #DEFAULT_scroll-list 가 있는 프레임 반환"""
    for ctx in [page, *page.frames]:
        try:
            if await ctx.locator(_SEL_SCROLL_CTR).count() > 0:
                logger.info(f"[Mail] 스크롤 프레임: {getattr(ctx, 'url', 'main')}")
                return ctx
        except Exception:
            continue
    return page


async def _open_and_download(
    page: Page,
    frame,
    chk,
    row_idx: int,
    save_dir: str,
) -> list[str]:
    """체크박스 클릭 → 제목 셀 우클릭 → 새 창으로 열기 → 모두저장 → 다운로드"""
    saved: list[str] = []

    # 1. 체크박스 클릭 (행 선택)
    await chk.click()
    await asyncio.sleep(0.4)

    # 2. 같은 프레임에서 행을 찾아 우클릭 (체크박스와 동일 프레임 보장)
    row = frame.locator(_SEL_MAIL_ROW).nth(row_idx)
    await row.click(button="right", timeout=10_000)
    await asyncio.sleep(0.5)

    # 3. "새 창으로 열기" / "새 창으로 보기" 메뉴 탐색 (모든 프레임)
    menu_item = None
    for label in ["새 창으로 열기", "새 창으로 보기"]:
        for ctx in [page, frame, *page.frames]:
            try:
                loc = ctx.locator(f'text="{label}"')
                if await loc.count() > 0:
                    menu_item = loc.first
                    break
            except Exception:
                continue
        if menu_item:
            break

    if menu_item is None:
        logger.warning("[Mail] 새 창 메뉴 미발견")
        return saved

    # 4. 새 창 열기
    try:
        async with page.context.expect_page(timeout=8_000) as new_pg:
            await menu_item.click()
        mail_page = await new_pg.value
        await mail_page.wait_for_load_state("domcontentloaded", timeout=15_000)
        await asyncio.sleep(3)
        logger.info("[Mail] 새 창 열림")
    except Exception as e:
        logger.warning(f"[Mail] 새 창 열기 실패: {e}")
        return saved

    # 5. 새 창 + 모든 프레임에서 '모두저장' 버튼 탐색 (로드 대기 포함)
    try:
        save_btn = None
        save_btn_ctx = mail_page
        for attempt in range(5):
            all_ctxs = [mail_page, *mail_page.frames]
            logger.info(f"[Mail] 새 창 프레임 수: {len(all_ctxs)} (시도 {attempt+1})")
            for ctx in all_ctxs:
                try:
                    for sel in [_SEL_SAVE_ALL, 'button:has-text("모두저장")']:
                        loc = ctx.locator(sel)
                        if await loc.count() > 0:
                            save_btn = loc.first
                            save_btn_ctx = ctx
                            logger.info(f"[Mail] 모두저장 버튼 발견 (selector: {sel})")
                            break
                except Exception:
                    continue
                if save_btn:
                    break
            if save_btn:
                break
            await asyncio.sleep(2)

        if save_btn is None:
            logger.warning("[Mail] 모두저장 버튼 없음 — 첨부파일 없는 메일")
            await mail_page.close()
            return saved

        # 6. 모두저장 클릭 → 저장첨부 팝업창(새 창) 열기
        logger.info("[Mail] 모두저장 클릭 → 저장첨부 팝업창 대기...")
        save_popup = None
        try:
            async with mail_page.context.expect_page(timeout=10_000) as popup_info:
                await save_btn.click()
            save_popup = await popup_info.value
            await save_popup.wait_for_load_state("domcontentloaded", timeout=15_000)
            await asyncio.sleep(2)
            logger.info("[Mail] 저장첨부 팝업창 열림")
        except Exception as e:
            logger.warning(f"[Mail] 저장첨부 팝업 새 창 열기 실패: {e}")
            await mail_page.close()
            return saved

        # 알림 팝업 자동 닫기 핸들러
        async def _dismiss_dialog(dialog):
            logger.info(f"[Mail] 알림 자동 닫기: {dialog.message}")
            await dialog.accept()
        save_popup.on("dialog", _dismiss_dialog)

        # 7. 저장첨부 팝업창에서 저장(S) 버튼 탐색
        save_confirm_btn = None
        for ctx in [save_popup, *save_popup.frames]:
            try:
                for sel in [
                    'button:has-text("저장(S)")',
                    'button[aria-label="저장(S)"]',
                    'button[aria-label="저장"]',
                    'button:has-text("저장")',
                    'button:has-text("확인")',
                ]:
                    loc = ctx.locator(sel)
                    if await loc.count() > 0 and await loc.first.is_visible():
                        save_confirm_btn = loc.first
                        logger.info(f"[Mail] 저장(S) 버튼 발견 ({sel}, frame={getattr(ctx, 'url', 'main')})")
                        break
            except Exception:
                continue
            if save_confirm_btn:
                break

        if save_confirm_btn is None:
            logger.warning("[Mail] 저장(S) 버튼 미발견")
            await save_popup.close()
            await mail_page.close()
            return saved

        # 8. 저장(S) 클릭 → 다운로드 캡처
        logger.info("[Mail] 저장(S) 클릭...")
        try:
            async with save_popup.expect_download(timeout=30_000) as dl_info:
                await save_confirm_btn.click()
            dl: Download = await dl_info.value
            saved = await _save_download(dl, save_dir)
        except Exception as e:
            logger.warning(f"[Mail] 다운로드 실패: {e}")

    except Exception as e:
        logger.warning(f"[Mail] 다운로드 실패: {e}")
    finally:
        try:
            if save_popup:
                await save_popup.close()
        except Exception:
            pass
        await mail_page.close()

    return saved


async def _save_download(dl: Download, save_dir: str) -> list[str]:
    """다운로드 파일을 FAdata 폴더에 저장 (zip이면 내부 Excel 추출)"""
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = dl.suggested_filename or f"mail_{ts}"
    dest  = os.path.join(save_dir, f"{ts}_{fname}")
    await dl.save_as(dest)
    logger.info(f"[Mail] 파일 저장: {dest}")

    ext = Path(fname).suffix.lower()

    # zip 파일이면 Excel만 추출
    if ext == ".zip":
        return _extract_excel_from_zip(dest, save_dir, ts)

    if ext in _EXCEL_EXTS:
        return [dest]

    # 확장자 불명확하면 일단 저장
    return [dest]


def _extract_excel_from_zip(zip_path: str, save_dir: str, ts: str) -> list[str]:
    """zip에서 Excel 파일만 꺼냅니다."""
    import zipfile
    saved = []
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                if Path(name).suffix.lower() in _EXCEL_EXTS:
                    dest = os.path.join(save_dir, f"{ts}_{os.path.basename(name)}")
                    with zf.open(name) as src, open(dest, "wb") as dst:
                        dst.write(src.read())
                    saved.append(dest)
                    logger.info(f"[Mail] zip 압축 해제: {dest}")
        os.remove(zip_path)  # 원본 zip 삭제
    except Exception as e:
        logger.warning(f"[Mail] zip 처리 실패: {e}")
        saved.append(zip_path)
    return saved


async def _scroll_mail_list(frame) -> int:
    """메일 목록 컨테이너를 아래로 스크롤하고 새 메일 수를 반환"""
    try:
        container = frame.locator(_SEL_SCROLL_CTR).first
        if await container.is_visible(timeout=2_000):
            await container.evaluate("el => el.scrollTop += el.clientHeight")
        await asyncio.sleep(1.5)
    except Exception:
        pass

    return await frame.locator(_SEL_MAIL_ROW).count()
