"""
HTML → PDF 변환 / HTML → ZIP 패키징 모듈 (Playwright 사용)
"""
import asyncio
import logging
import os
import zipfile

NETA_BASE_URL = "http://10.246.56.50:8000"

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


async def _check_neta_reachable(timeout: float = 4.0) -> bool:
    """NETA 서버 접근 가능 여부를 빠르게 확인합니다."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            resp = await client.get(NETA_BASE_URL)
            return resp.status_code < 500
    except Exception:
        return False


async def html_to_pdf(html_path: str, pdf_path: str, neta_enabled: bool = True) -> bool:
    """
    HTML 파일을 PDF로 변환합니다.
    neta_enabled=False 시 NETA 로딩 대기를 스킵합니다.
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

    # NETA 서버 자동 감지: neta_enabled=True 여도 실제 접속 불가 시 스킵
    if neta_enabled:
        neta_reachable = await _check_neta_reachable()
        if not neta_reachable:
            logger.warning("[PDF] NETA 서버 접근 불가 — NETA 로딩 스킵")
            neta_enabled = False
        else:
            logger.info("[PDF] NETA 서버 접근 가능 — NETA 로딩 활성화")

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
            if not neta_enabled:
                await page.add_init_script("window.NETA_ENABLED=false;")
                logger.info("[PDF] NETA 비활성화 모드")
            await page.goto(f"file:///{html_path.replace(os.sep, '/')}", wait_until="domcontentloaded", timeout=30000)

            # NETA prefetch 완료까지 대기 (최대 60초, 조기 완료 시 바로 진행)
            logger.info("[PDF] NETA 데이터 로딩 대기 중...")
            try:
                await page.wait_for_function(
                    "() => window.netaPrefetchComplete === true",
                    timeout=90000,
                )
                logger.info("[PDF] NETA 로딩 완료")
            except Exception:
                logger.warning("[PDF] NETA 대기 타임아웃(90s), 렌더링 계속 진행")

            # NETA 캐시 추출 → HTML에 주입 (오프라인 열람용)
            try:
                neta_cache_json = await page.evaluate(
                    "() => JSON.stringify(Object.fromEntries("
                    "  Object.entries(window.netaCache||{}).filter(([,v])=>v&&v.data!==undefined)"
                    "    .map(([k,v])=>[k,{data:v.data}])"
                    "))"
                )
                if neta_cache_json and neta_cache_json != "{}":
                    with open(html_path, encoding="utf-8") as _f:
                        _html = _f.read()
                    _inject = (
                        "<script>\n"
                        f"(function(){{var _nc={neta_cache_json};"
                        "Object.assign(typeof netaCache!=='undefined'?netaCache:(netaCache={}),"
                        "Object.fromEntries(Object.entries(_nc).map(([k,v])=>[k,v])));}})()\n"
                        "</script>\n"
                    )
                    _html = _html.replace("</body>", _inject + "</body>", 1)
                    with open(html_path, "w", encoding="utf-8") as _f:
                        _f.write(_html)
                    logger.info("[PDF] NETA 캐시 HTML 주입 완료")
            except Exception as _e:
                logger.warning(f"[PDF] NETA 캐시 주입 실패 (무시): {_e}")

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
                    '#tab-raw .tw { overflow-x:visible !important; overflow:visible !important; }',
                    '#tab-raw table { font-size:9px !important; table-layout:fixed; width:100%; }',
                    '#tab-raw th, #tab-raw td { white-space:normal !important; word-break:break-all; padding:2px 3px !important; }',
                    // 상단 고정 탭 네비게이션 바
                    '#pdf-nav { position:fixed; top:0; left:0; right:0; height:26px; background:linear-gradient(135deg,#1e3a5f 0%,#2d5a9e 100%); display:flex; align-items:center; padding:0 12px; gap:1px; z-index:9999; box-sizing:border-box; box-shadow:0 2px 6px rgba(0,0,0,0.3); }',
                    '#pdf-nav .nav-logo { color:#93c5fd; font-size:9px; font-weight:800; letter-spacing:1px; margin-right:10px; padding-right:10px; border-right:1px solid rgba(255,255,255,0.2); white-space:nowrap; }',
                    '#pdf-nav a { color:#fff; text-decoration:none; font-size:8.5px; font-weight:700; padding:3px 9px; border-radius:12px; white-space:nowrap; font-family:inherit; transition:all 0.15s; letter-spacing:0.3px; }',
                    '#pdf-nav a:hover { background:rgba(255,255,255,0.18); color:#fff; }',
                    'body { padding-top: 30px !important; }',
                ].join(' ');
                document.head.appendChild(style);

                // 상단 고정 탭 네비게이션 바 생성
                const NAV_TABS = [
                    ['overview', '전체 요약'],
                    ['station',  '문제 기지국'],
                    ['mute',     'MUTE 분석'],
                    ['drop',     'DROP 분석'],
                    ['daily',    '일별 상세'],
                    ['trend',    '추이 그래프'],
                    ['raw',      '원본 데이터'],
                ];
                const nav = document.createElement('div');
                nav.id = 'pdf-nav';
                nav.innerHTML = '<span class="nav-logo">통화품질 분석</span>'
                    + NAV_TABS.map(([id, label]) =>
                        '<a href="#tab-' + id + '">' + label + '</a>'
                    ).join('');
                document.body.insertBefore(nav, document.body.firstChild);

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
                    if (i > 0) el.style.pageBreakBefore = 'always';
                    const h = document.createElement('h2');
                    h.textContent = label;
                    h.style.cssText = 'font-size:15px;color:#1e3a5f;border-bottom:2px solid #1e3a5f;padding-bottom:6px;margin:0 0 14px';
                    el.insertBefore(h, el.firstChild);
                });

                // 원본 데이터 테이블 TAC(HEX) 컬럼 제거 + det-btn 열 제거
                // rawHead: Call(0),Date(1),Time(2),Feature(3),PLMN(4),ACT(5),TAC(HEX)(6),...,빈th(last)
                (function() {
                    const rawHead = document.getElementById('rawHead');
                    const rawBody = document.getElementById('rawBody');
                    if (!rawHead || !rawBody) return;
                    const hRow = rawHead.querySelector('tr');
                    if (hRow) {
                        const ths = hRow.querySelectorAll('th');
                        if (ths[6]) ths[6].remove();          // TAC(HEX)
                        const ths2 = hRow.querySelectorAll('th');
                        const last = ths2[ths2.length - 1];
                        if (last && last.textContent.trim() === '') last.remove(); // det-btn 헤더
                    }
                    rawBody.querySelectorAll('tr').forEach(row => {
                        const tds = row.querySelectorAll('td');
                        if (tds[6]) tds[6].remove();          // TAC(HEX)
                        // det-btn 셀 제거: 마지막 td 안에 .det-btn 이 있으면 삭제
                        const tds2 = row.querySelectorAll('td');
                        const lastTd = tds2[tds2.length - 1];
                        if (lastTd && lastTd.querySelector('.det-btn')) lastTd.remove();
                    });
                })();
            }""")

            # 차트 렌더링 기본 대기
            await page.wait_for_timeout(3000)

            # NETA 스피너가 모두 사라질 때까지 대기 (늦게 완료되는 fetch 대응, 최대 25s)
            try:
                await page.wait_for_function(
                    "() => document.querySelectorAll('.neta-loading').length === 0",
                    timeout=25000,
                )
                logger.info("[PDF] 모든 NETA 패널 로드 완료")
            except Exception:
                logger.warning("[PDF] NETA 패널 25s 대기 타임아웃 — 미완료 스피너 포함 PDF 생성")

            await page.pdf(
                path=pdf_path, format="A4", print_background=True, scale=0.75,
                margin={"top": "12mm", "bottom": "8mm", "left": "0mm", "right": "0mm"},
            )
            await browser.close()
        size_kb = os.path.getsize(pdf_path) // 1024 if os.path.exists(pdf_path) else 0
        logger.info(f"[PDF] 변환 완료: {pdf_path} ({size_kb}KB)")
        _compress_pdf(pdf_path)
        return True
    except Exception as e:
        logger.error(f"[PDF] 변환 실패: {type(e).__name__}: {e}", exc_info=True)
        return False


def _compress_pdf(pdf_path: str) -> None:
    """생성된 PDF를 pypdf로 인플레이스 압축합니다. pypdf 미설치 시 무시."""
    try:
        from pypdf import PdfWriter
        before = os.path.getsize(pdf_path)
        tmp = pdf_path + ".tmp"
        writer = PdfWriter(clone_from=pdf_path)
        writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
        for page in writer.pages:
            page.compress_content_streams()
        with open(tmp, "wb") as f:
            writer.write(f)
        after = os.path.getsize(tmp)
        if after < before:
            os.replace(tmp, pdf_path)
            logger.info(f"[PDF] 압축 완료: {before//1024}KB → {after//1024}KB")
        else:
            os.remove(tmp)
            logger.info(f"[PDF] 압축 효과 없음 ({before//1024}KB), 원본 유지")
    except ImportError:
        logger.debug("[PDF] pypdf 미설치 - 압축 건너뜀")
    except Exception as e:
        logger.warning(f"[PDF] 압축 실패 (원본 유지): {e}")


def generate_analysis_pdf(sn: str, html_path: str, save_dir: str) -> str | None:
    """
    분석 HTML을 PDF로 변환하여 저장합니다.
    반환: 생성된 PDF 경로, 실패 시 None
    """
    pdf_path = os.path.join(save_dir, f"{sn}_analysis.pdf")
    success = asyncio.run(html_to_pdf(html_path, pdf_path))
    return pdf_path if success else None
