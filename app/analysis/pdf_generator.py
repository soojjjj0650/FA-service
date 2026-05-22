"""
HTML → PDF 변환 / HTML → ZIP 패키징 모듈 (Playwright 사용)
"""
import asyncio
import logging
import os
import zipfile

logger = logging.getLogger(__name__)


def html_to_zip(html_path: str, zip_path: str, sn: str = "") -> bool:
    """
    HTML 파일을 zip으로 압축합니다.
    반환: 성공 여부
    """
    if not os.path.exists(html_path):
        logger.error(f"[ZIP] HTML 파일 없음: {html_path}")
        return False
    try:
        arcname = f"{sn}_analysis.html" if sn else os.path.basename(html_path)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            zf.write(html_path, arcname=arcname)
        size_kb = os.path.getsize(zip_path) // 1024
        logger.info(f"[ZIP] 생성 완료: {zip_path} ({size_kb} KB)")
        return True
    except Exception as e:
        logger.error(f"[ZIP] 생성 실패: {e}")
        return False


def generate_analysis_zip(sn: str, html_path: str, save_dir: str) -> str | None:
    """
    분석 HTML을 zip으로 압축하여 저장합니다.
    반환: 생성된 zip 경로, 실패 시 None
    """
    zip_path = os.path.join(save_dir, f"{sn}_analysis.zip")
    return zip_path if html_to_zip(html_path, zip_path, sn) else None


async def html_to_pdf(html_path: str, pdf_path: str) -> bool:
    """
    HTML 파일을 PDF로 변환합니다.
    반환: 성공 여부
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("[PDF] playwright 미설치 - pip install playwright 후 playwright install 실행 필요")
        return False

    if not os.path.exists(html_path):
        logger.error(f"[PDF] HTML 파일 없음: {html_path}")
        return False

    try:
        async with async_playwright() as p:
            # 브라우저 실행: Edge → Chromium → Linux headless_shell 순서로 시도
            browser = None
            for launch_kwargs in [
                {"channel": "msedge"},
                {},
                {"executable_path": "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell"},
            ]:
                try:
                    browser = await p.chromium.launch(**launch_kwargs)
                    break
                except Exception:
                    continue
            if browser is None:
                logger.error("[PDF] 사용 가능한 브라우저 없음")
                return False

            page = await browser.new_page()
            await page.goto(f"file:///{html_path.replace(os.sep, '/')}", wait_until="domcontentloaded", timeout=30000)

            # doParse가 완료되어 allRows가 채워질 때까지 대기 (최대 15초)
            try:
                await page.wait_for_function(
                    "() => typeof allRows !== 'undefined' && allRows.length > 0",
                    timeout=15000,
                )
            except Exception:
                logger.warning("[PDF] allRows 대기 타임아웃 — 그대로 진행")

            # lazy 렌더 강제 실행 + PDF용 전체 탭 표시 (raw 탭 제외)
            await page.evaluate("""() => {
                if (typeof renderStationTable === 'function') renderStationTable();
                if (typeof renderDropTab === 'function')      renderDropTab();
                if (typeof renderTrend === 'function')        renderTrend();

                const TAB_NAMES = {
                    overview: '전체 요약',
                    station:  '문제 기지국',
                    mute:     'MUTE 분석',
                    drop:     'DROP 분석',
                    daily:    '일별 상세',
                    trend:    '추이 그래프',
                };

                Object.entries(TAB_NAMES).forEach(([id, label], i) => {
                    const el = document.getElementById('tab-' + id);
                    if (!el) return;
                    el.style.display = 'block';
                    if (i > 0) {
                        el.style.pageBreakBefore = 'always';
                        const h = document.createElement('h2');
                        h.textContent = label;
                        h.style.cssText = 'font-size:15px;color:#1e3a5f;border-bottom:2px solid #1e3a5f;padding-bottom:6px;margin:0 0 14px';
                        el.insertBefore(h, el.firstChild);
                    }
                });

                // 원본 데이터 탭은 PDF에서 제외 (데이터 많아 수백 페이지)
                const rawTab = document.getElementById('tab-raw');
                if (rawTab) rawTab.style.display = 'none';

                const tabBar = document.querySelector('.tab-bar');
                if (tabBar) tabBar.style.display = 'none';
            }""")

            # 차트 렌더링 완료 대기
            await page.wait_for_timeout(2500)
            await page.pdf(path=pdf_path, format="A4", print_background=True)
            await browser.close()
        logger.info(f"[PDF] 변환 완료: {pdf_path}")
        return True
    except Exception as e:
        logger.error(f"[PDF] 변환 실패: {type(e).__name__}: {e}", exc_info=True)
        return False


def generate_analysis_pdf(sn: str, html_path: str, save_dir: str) -> str | None:
    """
    분석 HTML을 PDF로 변환하여 저장합니다.
    반환: 생성된 PDF 경로, 실패 시 None
    """
    pdf_path = os.path.join(save_dir, f"{sn}_analysis.pdf")
    success = asyncio.run(html_to_pdf(html_path, pdf_path))
    return pdf_path if success else None
