"""
Samsung.net 메일 다운로더

동작 흐름:
  1. www.samsung.net 로그인 (ID/PW)
  2. 메일 섹션으로 이동
  3. "FA 미결건" 폴더 클릭
  4. 미열람(새) 메일 중 Excel 첨부파일이 있는 것 다운로드
  5. MAIL_SAVE_DIR (기본: CSV_DOWNLOAD_PATH/FAdata) 에 저장
  6. 이미 다운로드한 메일 ID는 .downloaded_ids 파일로 중복 방지
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, BrowserContext

from app.config import settings

logger = logging.getLogger(__name__)

_AUTH_STATE_PATH = Path("data") / "sessions" / "mail_auth_state.json"
_DOWNLOADED_IDS_FILE = Path("data") / "sessions" / "mail_downloaded_ids.json"

# 다운로드할 첨부파일 확장자
_EXCEL_EXTS = {".xlsx", ".xls", ".xlsm"}


def _get_save_dir() -> str:
    base = settings.MAIL_SAVE_DIR or os.path.join(settings.CSV_DOWNLOAD_PATH, "FAdata")
    os.makedirs(base, exist_ok=True)
    return base


def _load_downloaded_ids() -> set:
    try:
        if _DOWNLOADED_IDS_FILE.exists():
            with open(_DOWNLOADED_IDS_FILE, encoding="utf-8") as f:
                return set(json.load(f))
    except Exception:
        pass
    return set()


def _save_downloaded_ids(ids: set) -> None:
    _DOWNLOADED_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_DOWNLOADED_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(ids), f, ensure_ascii=False)


async def download_mail_attachments() -> list[str]:
    """
    FA 미결건 폴더의 새 메일에서 Excel 첨부파일을 다운로드합니다.
    저장된 파일 경로 목록을 반환합니다.
    """
    save_dir = _get_save_dir()
    downloaded_ids = _load_downloaded_ids()
    saved_files: list[str] = []

    _AUTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    pw = await async_playwright().start()
    try:
        # ── 브라우저 실행 ────────────────────────────────────────────────────
        launch_kwargs: dict = {
            "headless": settings.MAIL_HEADLESS,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--start-maximized",
            ],
        }
        edge_path = settings.EDGE_EXECUTABLE_PATH
        if edge_path and os.path.exists(edge_path):
            launch_kwargs["executable_path"] = edge_path

        browser = await pw.chromium.launch(**launch_kwargs)

        ctx_kwargs: dict = {
            "accept_downloads": True,
            "viewport": None,
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
            ),
        }
        if _AUTH_STATE_PATH.exists():
            ctx_kwargs["storage_state"] = str(_AUTH_STATE_PATH)

        context = await browser.new_context(**ctx_kwargs)
        page = await context.new_page()

        try:
            # ── 1. samsung.net 로그인 ────────────────────────────────────────
            await _do_login(page, context)

            # ── 2. 메일 섹션으로 이동 ────────────────────────────────────────
            await _navigate_to_mail(page)

            # ── 3. FA 미결건 폴더 클릭 ──────────────────────────────────────
            await _open_folder(page, settings.MAIL_FOLDER_NAME)

            # ── 4. 새 메일 목록 수집 + 첨부파일 다운로드 ────────────────────
            new_files = await _download_new_attachments(
                page, context, save_dir, downloaded_ids
            )
            saved_files.extend(new_files)

            # ── 5. 다운로드 완료 ID 저장 ─────────────────────────────────────
            _save_downloaded_ids(downloaded_ids)
            logger.info(f"[Mail] 다운로드 완료: {len(saved_files)}개 → {save_dir}")

        finally:
            await _debug_screenshot(page, save_dir, "mail_final")
            await context.close()
            await browser.close()

    finally:
        await pw.stop()

    return saved_files


# ─── 내부 헬퍼 ────────────────────────────────────────────────────────────────

async def _do_login(page: Page, context: BrowserContext) -> None:
    """www.samsung.net ID/PW 로그인"""
    logger.info("[Mail] samsung.net 접속 중...")
    await page.goto(settings.MAIL_URL, wait_until="domcontentloaded", timeout=30_000)
    await asyncio.sleep(2)

    pw_loc = page.locator(".login-pw input, input[type='password']")
    if await pw_loc.count() > 0:
        logger.info("[Mail] ID/PW 입력 중...")
        id_loc = page.locator(".login-id input, input[type='text'], input[name='userId'], input[name='username']")
        if await id_loc.count() > 0:
            await id_loc.first.click(click_count=3)
            await id_loc.first.type(settings.MAIL_USERNAME, delay=50)
        await pw_loc.first.click(click_count=3)
        await pw_loc.first.type(settings.MAIL_PASSWORD, delay=50)
        await pw_loc.first.press("Enter")
        await asyncio.sleep(4)
        logger.info("[Mail] 로그인 완료")
    else:
        logger.info("[Mail] 이미 로그인됨")

    await context.storage_state(path=str(_AUTH_STATE_PATH))


async def _navigate_to_mail(page: Page) -> None:
    """메인 포털에서 메일 섹션으로 이동"""
    logger.info("[Mail] 메일 섹션 이동 중...")
    await _debug_screenshot(page, _get_save_dir(), "mail_after_login")

    # 메일 링크 탐색 (다양한 셀렉터 시도)
    mail_selectors = [
        "a[href*='mail']",
        "a:has-text('Mail')",
        "a:has-text('메일')",
        "[class*='mail']:visible",
        "[id*='mail']:visible",
    ]
    for sel in mail_selectors:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=2_000):
                logger.info(f"[Mail] 메일 링크 클릭: {sel}")
                async with page.expect_navigation(timeout=15_000):
                    await loc.click()
                await asyncio.sleep(3)
                await _debug_screenshot(page, _get_save_dir(), "mail_section")
                return
        except Exception:
            continue

    # URL 직접 접근 시도
    mail_urls = [
        f"{settings.MAIL_URL}/mail",
        f"{settings.MAIL_URL}/groupware/mail",
        f"{settings.MAIL_URL}/ens/mail",
    ]
    for url in mail_urls:
        try:
            logger.info(f"[Mail] 직접 URL 시도: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=15_000)
            await asyncio.sleep(3)
            # 메일함 목록이 보이면 성공
            if await page.locator("[class*='folder'], [class*='Folder'], [class*='mailbox']").count() > 0:
                logger.info(f"[Mail] 메일 페이지 진입 성공: {url}")
                await _debug_screenshot(page, _get_save_dir(), "mail_section")
                return
        except Exception as e:
            logger.debug(f"[Mail] URL 시도 실패 {url}: {e}")

    logger.warning("[Mail] 메일 섹션 이동 실패 — 현재 페이지에서 계속 시도")


async def _open_folder(page: Page, folder_name: str) -> None:
    """지정한 폴더(예: FA 미결건)를 클릭해 메일 목록 로드"""
    logger.info(f"[Mail] '{folder_name}' 폴더 찾는 중...")
    await _debug_screenshot(page, _get_save_dir(), "mail_before_folder")

    # 텍스트로 폴더 탐색 (모든 프레임 포함)
    for frame in [page] + list(page.frames):
        try:
            loc = frame.locator(f"text='{folder_name}'").first
            if await loc.is_visible(timeout=3_000):
                logger.info(f"[Mail] 폴더 클릭: {folder_name}")
                await loc.click()
                await asyncio.sleep(3)
                await _debug_screenshot(page, _get_save_dir(), "mail_folder_opened")
                return
        except Exception:
            continue

    # contains 방식
    for frame in [page] + list(page.frames):
        try:
            loc = frame.locator(f":text-is('{folder_name}')").first
            if await loc.is_visible(timeout=2_000):
                await loc.click()
                await asyncio.sleep(3)
                return
        except Exception:
            continue

    logger.warning(f"[Mail] '{folder_name}' 폴더를 찾지 못했습니다. 스크린샷 확인 필요")


async def _download_new_attachments(
    page: Page,
    context: BrowserContext,
    save_dir: str,
    downloaded_ids: set,
) -> list[str]:
    """폴더 목록에서 미열람 메일의 Excel 첨부파일을 다운로드"""
    saved: list[str] = []
    await _debug_screenshot(page, save_dir, "mail_list")

    # 메일 행 탐색 (읽지 않은 메일 우선)
    mail_row_selectors = [
        "tr.unread", "tr[class*='unread']",
        "li.unread", "li[class*='unread']",
        "[class*='mail-item']:not([class*='read'])",
        "tr[data-read='false']", "tr[data-readed='0']",
        # 읽지 않은 것 구분 안 되면 전체
        "tr[data-uid]", "tr[data-mail-id]", "tr[data-seq]",
    ]

    mail_rows = []
    for frame in [page] + list(page.frames):
        for sel in mail_row_selectors:
            try:
                rows = frame.locator(sel)
                cnt = await rows.count()
                if cnt > 0:
                    mail_rows = [(frame, rows, cnt)]
                    logger.info(f"[Mail] 메일 행 {cnt}개 발견 (selector: {sel})")
                    break
            except Exception:
                continue
        if mail_rows:
            break

    if not mail_rows:
        logger.info("[Mail] 메일 행을 찾지 못했습니다 — 새 메일 없음")
        return saved

    frame, rows, cnt = mail_rows[0]
    processed = 0

    for i in range(min(cnt, 30)):  # 최대 30개 처리
        try:
            row = rows.nth(i)

            # 메일 고유 ID 추출
            mail_id = (
                await row.get_attribute("data-uid")
                or await row.get_attribute("data-mail-id")
                or await row.get_attribute("data-seq")
                or await row.get_attribute("data-id")
                or f"row_{i}"
            )

            if mail_id in downloaded_ids:
                logger.debug(f"[Mail] 이미 처리된 메일 건너뜀: {mail_id}")
                continue

            # 메일 클릭 (새 탭이 열릴 수 있음)
            logger.info(f"[Mail] 메일 {i+1}/{cnt} 클릭 (id={mail_id})")
            async with context.expect_page() as new_page_info:
                await row.click()
                await asyncio.sleep(0.5)

            try:
                mail_page = await new_page_info.value
                await mail_page.wait_for_load_state("domcontentloaded", timeout=15_000)
            except Exception:
                # 새 탭이 아니라 같은 페이지에서 열린 경우
                mail_page = page

            await asyncio.sleep(2)
            await _debug_screenshot(mail_page, save_dir, f"mail_open_{i}")

            # 첨부파일 다운로드
            files = await _download_attachments_from_mail(mail_page, save_dir)
            if files:
                saved.extend(files)
                downloaded_ids.add(mail_id)
                processed += 1
                logger.info(f"[Mail] 첨부파일 저장: {files}")

            # 새 탭이면 닫기
            if mail_page != page:
                await mail_page.close()

        except Exception as e:
            logger.warning(f"[Mail] 메일 {i+1} 처리 중 오류: {e}")
            continue

    logger.info(f"[Mail] 처리 완료 — {processed}건 메일에서 {len(saved)}개 파일 저장")
    return saved


async def _download_attachments_from_mail(page: Page, save_dir: str) -> list[str]:
    """열려 있는 메일 페이지에서 Excel 첨부파일을 다운로드"""
    saved: list[str] = []

    attach_selectors = [
        "a[href*='.xlsx']", "a[href*='.xls']",
        "[class*='attach']:has-text('.xlsx')",
        "[class*='attach']:has-text('.xls')",
        "a[class*='attach']", "a[class*='file']",
        "[class*='attachment'] a",
        "a[download]",
    ]

    for frame in [page] + list(page.frames):
        for sel in attach_selectors:
            try:
                links = frame.locator(sel)
                cnt = await links.count()
                for j in range(cnt):
                    link = links.nth(j)
                    href = await link.get_attribute("href") or ""
                    text = (await link.inner_text()).strip()
                    name = os.path.basename(href.split("?")[0]) or text

                    # Excel 확장자 확인
                    ext = Path(name).suffix.lower()
                    if ext not in _EXCEL_EXTS:
                        # href에 확장자 없으면 텍스트로 판단
                        if not any(k in text.lower() for k in [".xlsx", ".xls", "excel"]):
                            continue

                    logger.info(f"[Mail] 첨부파일 다운로드 시도: {name}")
                    try:
                        async with page.expect_download(timeout=30_000) as dl_info:
                            await link.click()
                        dl = await dl_info.value

                        # 파일명 결정 (타임스탬프 접두사)
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        fname = dl.suggested_filename or name or f"mail_attach_{ts}.xlsx"
                        if Path(fname).suffix.lower() not in _EXCEL_EXTS:
                            fname += ".xlsx"
                        dest = os.path.join(save_dir, f"{ts}_{fname}")
                        await dl.save_as(dest)
                        saved.append(dest)
                        logger.info(f"[Mail] 저장 완료: {dest}")
                    except Exception as e:
                        logger.warning(f"[Mail] 다운로드 실패 ({name}): {e}")
            except Exception:
                continue
        if saved:
            break

    return saved


async def _debug_screenshot(page: Page, save_dir: str, tag: str) -> None:
    try:
        ts = datetime.now().strftime("%H%M%S")
        path = os.path.join(save_dir, f"debug_{tag}_{ts}.png")
        await page.screenshot(path=path)
        logger.debug(f"[Mail] 스크린샷: {path}")
    except Exception:
        pass
