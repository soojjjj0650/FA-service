"""
Log Analyzer Runner - log_analyzer.html에 CSV 데이터를 주입하여 자동 로드 HTML 생성
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

_TEMPLATE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "log_analyzer.html")
)


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

        # </body> 직전에 자동 실행 스크립트 주입
        # body 끝에 위치하므로 doParse는 이미 정의된 상태 → 직접 호출
        inject = (
            "<script>\n"
            "(function(){\n"
            f"  var _d={json.dumps(csv_content)};\n"
            f"  var _f={json.dumps(sn+'_inputdata.csv')};\n"
            "  function _run(){if(typeof doParse==='function'){doParse(_d,_f);}}\n"
            "  if(document.readyState==='complete'||document.readyState==='interactive'){\n"
            "    setTimeout(_run,0);\n"
            "  } else {\n"
            "    window.addEventListener('DOMContentLoaded',_run);\n"
            "  }\n"
            "})();\n"
            "</script>\n"
        )
        html = html.replace("</body>", inject + "</body>", 1)

        os.makedirs(save_dir, exist_ok=True)
        out_path = os.path.join(save_dir, f"{sn}_analysis.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"분석 HTML 생성 완료: {out_path}")
        return out_path

    except Exception as e:
        logger.error(f"분석 HTML 생성 실패 [{type(e).__name__}]: {e}", exc_info=True)
        return None
