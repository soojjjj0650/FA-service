"""
HTML → PDF 변환 모듈 (Playwright 사용)
"""
import asyncio
import logging
import os

logger = logging.getLogger(__name__)


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
            # Edge가 이미 설치되어 있으면 Edge 사용, 없으면 Chromium 사용
            try:
                browser = await p.chromium.launch(channel="msedge")
            except Exception:
                browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(f"file:///{html_path.replace(os.sep, '/')}", wait_until="networkidle", timeout=30000)
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
