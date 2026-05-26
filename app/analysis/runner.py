"""
Log Analyzer Runner - log_analyzer.html에 CSV 데이터를 주입하여 자동 로드 HTML 생성
"""
import json
import logging
import os
import re

logger = logging.getLogger(__name__)

_TEMPLATE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "log_analyzer.html")
)

_CHARTJS_CACHE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "chartjs.cache.js")
)
_CHARTJS_URL = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"

# ─── SVG 아이콘 정의 (Font Awesome 대체) ─────────────────────────────────────
_SVG = {
    "clipboard":    ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512">'
                     '<path d="M280 64h40c35.3 0 64 28.7 64 64V448c0 35.3-28.7 64-64 64H64'
                     'c-35.3 0-64-28.7-64-64V128C0 92.7 28.7 64 64 64h40 9.6C121 27.5 153.3 0'
                     ' 192 0s71 27.5 78.4 64H280zM64 112c-8.8 0-16 7.2-16 16V448c0 8.8 7.2 16'
                     ' 16 16H320c8.8 0 16-7.2 16-16V128c0-8.8-7.2-16-16-16H304v24c0 13.3-10.7'
                     ' 24-24 24H104c-13.3 0-24-10.7-24-24V112H64zm128-8a24 24 0 1 0 0-48 24 24'
                     ' 0 1 0 0 48z"/></svg>'),
    "download":     ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
                     '<path d="M288 32c0-17.7-14.3-32-32-32s-32 14.3-32 32V274.7l-73.4-73.4'
                     'c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3l128 128c12.5 12.5 32.8'
                     ' 12.5 45.3 0l128-128c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L288'
                     ' 274.7V32zM64 352c-35.3 0-64 28.7-64 64v32c0 35.3 28.7 64 64 64H448'
                     'c35.3 0 64-28.7 64-64V416c0-35.3-28.7-64-64-64H346.5l-45.3 45.3'
                     'c-25 25-65.5 25-90.5 0L165.5 352H64zm368 56a24 24 0 1 1 0 48 24 24'
                     ' 0 1 1 0-48z"/></svg>'),
    "copy":         ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512">'
                     '<path d="M208 0H332.1c12.7 0 24.9 5.1 33.9 14.1l67.9 67.9c9 9 14.1 21.2'
                     ' 14.1 33.9V336c0 26.5-21.5 48-48 48H208c-26.5 0-48-21.5-48-48V48'
                     'c0-26.5 21.5-48 48-48zM48 128h80v64H64V448H256V416h64v48c0 26.5-21.5'
                     ' 48-48 48H48c-26.5 0-48-21.5-48-48V176c0-26.5 21.5-48 48-48z"/></svg>'),
    "circle-check": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
                     '<path d="M256 512A256 256 0 1 0 256 0a256 256 0 1 0 0 512zM369 209'
                     'L241 337c-9.4 9.4-24.6 9.4-33.9 0l-64-64c-9.4-9.4-9.4-24.6 0-33.9'
                     's24.6-9.4 33.9 0l47 47L335 175c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0'
                     ' 33.9z"/></svg>'),
    "circle-xmark": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
                     '<path d="M256 512A256 256 0 1 0 256 0a256 256 0 1 0 0 512zM175 175'
                     'c9.4-9.4 24.6-9.4 33.9 0l47 47 47-47c9.4-9.4 24.6-9.4 33.9 0s9.4'
                     ' 24.6 0 33.9l-47 47 47 47c9.4 9.4 9.4 24.6 0 33.9s-24.6 9.4-33.9'
                     ' 0l-47-47-47 47c-9.4 9.4-24.6 9.4-33.9 0s-9.4-24.6 0-33.9l47-47'
                     '-47-47c-9.4-9.4-9.4-24.6 0-33.9z"/></svg>'),
    "phone":        ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
                     '<path d="M164.9 24.6c-7.7-18.6-28-28.5-47.4-23.2l-88 24C12.1 30.2 0 46'
                     ' 0 64C0 311.4 200.6 512 448 512c18 0 33.8-12.1 38.6-29.5l24-88'
                     'c5.3-19.4-4.6-39.7-23.2-47.4l-96-40c-16.3-6.8-35.2-2.1-46.3 11.6'
                     'L304.7 368C234.3 334.7 177.3 277.7 144 207.3L193.3 167'
                     'c13.7-11.2 18.4-30 11.6-46.3l-40-96z"/></svg>'),
    "tower-cell":   ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512">'
                     '<path d="M384 0c-17.7 0-32 14.3-32 32s14.3 32 32 32c123.7 0 224 100.3'
                     ' 224 224c0 17.7 14.3 32 32 32s32-14.3 32-32C672 129.2 541.8 0 384 0z'
                     'M384 128c-17.7 0-32 14.3-32 32s14.3 32 32 32c53 0 96 43 96 96'
                     'c0 17.7 14.3 32 32 32s32-14.3 32-32c0-88.4-71.6-160-160-160z'
                     'M288 288c0-53 43-96 96-96c17.7 0 32-14.3 32-32s-14.3-32-32-32'
                     'c-88.4 0-160 71.6-160 160c0 17.7 14.3 32 32 32s32-14.3 32-32z'
                     'M80 384H48c-26.5 0-48 21.5-48 48s21.5 48 48 48H528c26.5 0 48-21.5'
                     ' 48-48s-21.5-48-48-48H192L154.7 288.6C152.9 280.9 146 275.2 138.1'
                     ' 275.2H89.9c-7.9 0-14.8 5.7-16.6 13.4L56 384H80z"/></svg>'),
}


def _svg_data_uri(name: str) -> str:
    svg = _SVG[name].replace('"', "'").replace("#", "%23").replace("<", "%3C").replace(">", "%3E").replace(" ", "%20")
    return f"url(\"data:image/svg+xml,{svg}\")"


def _fa_inline_css() -> str:
    rules = [
        "i.fa,i.fa-solid{"
        "display:inline-block;width:1em;height:1em;"
        "background-color:currentColor;"
        "-webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;"
        "-webkit-mask-position:center;mask-position:center;"
        "-webkit-mask-size:contain;mask-size:contain;"
        "vertical-align:-0.125em}"
    ]
    mapping = {
        "i.fa.fa-clipboard,i.fa-solid.fa-clipboard": "clipboard",
        "i.fa.fa-download,i.fa-solid.fa-download": "download",
        "i.fa.fa-copy,i.fa-solid.fa-copy": "copy",
        "i.fa-solid.fa-circle-check": "circle-check",
        "i.fa-solid.fa-circle-xmark": "circle-xmark",
        "i.fa-solid.fa-phone": "phone",
        "i.fa-solid.fa-tower-cell": "tower-cell",
    }
    for sel, name in mapping.items():
        uri = _svg_data_uri(name)
        rules.append(f"{sel}{{-webkit-mask-image:{uri};mask-image:{uri}}}")
    return "<style>" + "".join(rules) + "</style>"


def _get_chartjs() -> str | None:
    """Chart.js를 로컬 캐시에서 읽거나 CDN에서 다운로드합니다."""
    if os.path.exists(_CHARTJS_CACHE_PATH):
        try:
            with open(_CHARTJS_CACHE_PATH, encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    try:
        import httpx
        r = httpx.get(_CHARTJS_URL, timeout=15, follow_redirects=True)
        if r.status_code == 200:
            content = r.text
            with open(_CHARTJS_CACHE_PATH, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Chart.js 다운로드 완료 → {_CHARTJS_CACHE_PATH}")
            return content
    except Exception as e:
        logger.warning(f"Chart.js 다운로드 실패 (오프라인 모드로 계속): {e}")
    return None


def _make_offline(html: str) -> str:
    """CDN 리소스를 인라인으로 교체하여 오프라인에서도 동작하는 HTML로 변환합니다."""

    # 1. Chart.js CDN → 인라인 <script>
    chartjs = _get_chartjs()
    if chartjs:
        html = re.sub(
            r'<script\s+src=["\']https://cdnjs\.cloudflare\.com/ajax/libs/Chart\.js/[^"\']+["\']></script>',
            f"<script>{chartjs}</script>",
            html,
        )

    # 2. Font Awesome CDN → 인라인 SVG CSS
    html = re.sub(
        r'<link[^>]+font-awesome[^>]+/>',
        _fa_inline_css(),
        html,
    )

    # 3. Pretendard 폰트 → 제거 (시스템 폰트로 fallback)
    html = re.sub(r'<link[^>]+pretendard[^>]+/>', '', html)

    # 4. body/html 기본 폰트를 시스템 폰트로 교체
    html = html.replace(
        "font-family:'Pretendard'",
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif",
    ).replace(
        'font-family:"Pretendard"',
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif",
    )

    return html


def generate_analysis_html(sn: str, csv_path: str, save_dir: str) -> str | None:
    """
    CSV 파일 내용을 log_analyzer.html에 주입하여 자동 로드 HTML을 생성합니다.
    반환: 생성된 HTML 파일 경로, 실패 시 None
    """
    if not os.path.exists(_TEMPLATE_PATH):
        logger.error(f"log_analyzer.html 템플릿 없음: {_TEMPLATE_PATH}")
        return None

    # CSV 읽기 (인코딩 순차 시도)
    csv_content = None
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr", "latin-1"):
        try:
            with open(csv_path, encoding=enc) as f:
                csv_content = f.read()
            break
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    if csv_content is None:
        logger.error(f"CSV 읽기 실패: {csv_path}")
        return None

    try:
        with open(_TEMPLATE_PATH, encoding="utf-8") as f:
            html = f.read()

        # CDN 리소스 인라인화
        html = _make_offline(html)

        # </body> 직전에 CSV 데이터 자동 실행 스크립트 주입
        csv_json = json.dumps(csv_content).replace("</script>", "<\\/script>")
        inject = (
            "<script>\n"
            "(function(){\n"
            f"  var _d={csv_json};\n"
            f"  var _f={json.dumps(sn+'_inputdata.csv')};\n"
            "  function _run(){\n"
            "    console.log('[FA] _run called, doParse type:', typeof doParse);\n"
            "    console.log('[FA] csv length:', _d.length);\n"
            "    if(typeof doParse==='function'){\n"
            "      try{ doParse(_d,_f); console.log('[FA] doParse OK'); }\n"
            "      catch(e){ console.error('[FA] doParse error:', e); }\n"
            "    } else { console.error('[FA] doParse not found'); }\n"
            "  }\n"
            "  if(document.readyState==='complete'||document.readyState==='interactive'){\n"
            "    setTimeout(_run,0);\n"
            "  } else {\n"
            "    window.addEventListener('DOMContentLoaded',_run);\n"
            "  }\n"
            "})();\n"
            "</script>\n"
        )
        last_body = html.rfind("</body>")
        if last_body >= 0:
            html = html[:last_body] + inject + html[last_body:]

        os.makedirs(save_dir, exist_ok=True)
        out_path = os.path.join(save_dir, f"{sn}_analysis.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"분석 HTML 생성 완료 (오프라인 가능): {out_path}")
        return out_path

    except Exception as e:
        logger.error(f"분석 HTML 생성 실패 [{type(e).__name__}]: {e}", exc_info=True)
        return None
