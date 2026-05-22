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
            await page.goto(f"file:///{html_path.replace(os.sep, '/')}", wait_until="networkidle", timeout=30000)

            # 모든 탭 펼치기: lazy render 강제 실행 + 전체 표시
            await page.evaluate("""() => {
                // lazy render 강제 실행 (탭 클릭 시에만 그려지는 것들)
                if (typeof renderTrend === 'function')        renderTrend();
                if (typeof renderStationTable === 'function') renderStationTable();
                if (typeof renderDropTab === 'function')      renderDropTab();
                if (typeof renderRaw === 'function')          renderRaw();

                const TAB_NAMES = {
                    overview: '전체 요약',
                    station:  '문제 기지국',
                    mute:     'MUTE 분석',
                    drop:     'DROP 분석',
                    daily:    '일별 상세',
                    trend:    '추이 그래프',
                    raw:      '원본 데이터',
                };

                Object.entries(TAB_NAMES).forEach(([id, label], i) => {
                    const el = document.getElementById('tab-' + id);
                    if (!el) return;
                    el.style.display = 'block';
                    // 두 번째 탭부터 페이지 구분
                    if (i > 0) {
                        el.style.pageBreakBefore = 'always';
                        // 탭 구분 제목 추가
                        const h = document.createElement('h2');
                        h.textContent = label;
                        h.style.cssText = 'font-size:15px;color:#1e3a5f;border-bottom:2px solid #1e3a5f;padding-bottom:6px;margin:0 0 14px';
                        el.insertBefore(h, el.firstChild);
                    }
                });

                // 탭 바 숨기기 (PDF에서 불필요)
                const tabBar = document.querySelector('.tab-bar');
                if (tabBar) tabBar.style.display = 'none';

                // tab-content 테두리 전체 적용
                const tabContent = document.querySelector('.tab-content');
                if (tabContent) tabContent.style.borderRadius = '8px';
            }""")

            # 렌더링 완료 대기
            await page.wait_for_timeout(1500)
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
