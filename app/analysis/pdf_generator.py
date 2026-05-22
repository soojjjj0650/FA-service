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

            # lazy 렌더 강제 실행 + PDF용 전체 탭 표시
            await page.evaluate("""() => {
                if (typeof renderStationTable === 'function') renderStationTable();
                if (typeof renderDropTab === 'function')      renderDropTab();
                if (typeof renderTrend === 'function')        renderTrend();

                // 원본 데이터: RP가 const라 재할당 불가 → slice 오버라이드로 전체 표시
                if (typeof rawFiltered !== 'undefined' && rawFiltered.length > 0) {
                    rawPage = 1;
                    const origSlice = rawFiltered.slice.bind(rawFiltered);
                    rawFiltered.slice = function() { return origSlice(); };
                    if (typeof renderRaw === 'function') renderRaw();
                    rawFiltered.slice = origSlice;
                    const pager = document.getElementById('rawPager');
                    if (pager) pager.style.display = 'none';
                }

                const style = document.createElement('style');
                style.textContent = [
                    '#trendContent canvas { max-width:100% !important; }',
                    '#trendContent > div { overflow:hidden !important; }',
                    // 원본 데이터 테이블: 폰트 축소 + 텍스트 줄바꿈 허용 → 가로 맞춤
                    '#tab-raw table { font-size:9px !important; table-layout:fixed; width:100%; }',
                    '#tab-raw th, #tab-raw td { white-space:normal !important; word-break:break-all; padding:2px 3px !important; }',
                ].join(' ');
                document.head.appendChild(style);

                // 기지국 테이블 TAC(HEX) 컬럼 제거
                // 헤더 1행: '기지국 정보' colspan 6→5
                // 헤더 2행: PLMN(0),ACT(1),TAC(HEX)(2) → index 2 제거
                // 데이터행: #(0),상태(1),PLMN(2),ACT(3),TAC(HEX)(4) → index 4 제거
                (function() {
                    const stHead = document.getElementById('stHead');
                    const stBody = document.getElementById('stBody');
                    if (!stHead || !stBody) return;
                    const hRows = stHead.querySelectorAll('tr');
                    if (hRows[0]) {
                        hRows[0].querySelectorAll('th').forEach(th => {
                            if (th.colSpan > 1 && th.textContent.includes('기지국')) {
                                th.colSpan = Math.max(1, th.colSpan - 1);
                            }
                        });
                    }
                    if (hRows[1]) {
                        const ths = hRows[1].querySelectorAll('th');
                        if (ths[2]) ths[2].remove();
                    }
                    stBody.querySelectorAll('tr').forEach(row => {
                        const tds = row.querySelectorAll('td');
                        if (tds[4]) tds[4].remove();
                    });
                })();

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
                    if (i > 0) {
                        el.style.pageBreakBefore = 'always';
                        const h = document.createElement('h2');
                        h.textContent = label;
                        h.style.cssText = 'font-size:15px;color:#1e3a5f;border-bottom:2px solid #1e3a5f;padding-bottom:6px;margin:0 0 14px';
                        el.insertBefore(h, el.firstChild);
                    }
                });

                // 원본 데이터 테이블 TAC(HEX) 컬럼 제거 (index 6)
                // rawHead: Call(0),Date(1),Time(2),Feature(3),PLMN(4),ACT(5),TAC(HEX)(6),...
                (function() {
                    const rawHead = document.getElementById('rawHead');
                    const rawBody = document.getElementById('rawBody');
                    if (!rawHead || !rawBody) return;
                    const hRow = rawHead.querySelector('tr');
                    if (hRow) { const ths = hRow.querySelectorAll('th'); if (ths[6]) ths[6].remove(); }
                    rawBody.querySelectorAll('tr').forEach(row => {
                        const tds = row.querySelectorAll('td');
                        if (tds[6]) tds[6].remove();
                    });
                })();
            }""")

            # 차트 + 원본 데이터 렌더링 완료 대기
            await page.wait_for_timeout(3000)
            await page.pdf(
                path=pdf_path, format="A4", print_background=True, scale=0.75,
                margin={"top": "8mm", "bottom": "8mm", "left": "0mm", "right": "0mm"},
            )
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
