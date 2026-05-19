"""
Data Processor - CSV feature 데이터를 가공

처리 흐름:
  1. QueryResult.csv_path 에서 CSV 읽기 (Date / Time / feature / custom_value)
  2. feature 별로 그룹화
  3. custom_value JSON 파싱 → feature 매핑 컬럼 추출
  4. AI Agent 전송용 텍스트 + 챗봇 표시용 HTML 테이블 생성
"""

import csv
import json
import logging
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from app.scraper.query_runner import QueryResult
from app.processor.code_mappings import apply_code

logger = logging.getLogger(__name__)


# ─── feature별 컬럼 매핑 (표시명 → custom_value JSON 키) ─────────────────────
# __date__ / __time__ 은 CSV 행의 Date / Time 컬럼을 직접 사용
FEATURE_COLUMNS: dict[str, OrderedDict] = {
    "MUTE": OrderedDict([
        ("Date",  "__date__"),
        ("Time",  "__time__"),
        ("PLMN",  "PLMN"),
        ("ACT",   "ACT_"),
        ("TAC",   "TAC_"),
        ("LAC",   "LAC_"),
        ("PCI",   "PhID"),
        ("DLCh",  "DLCh"),
        ("Band",  "LBND"),
        ("UBMT",  "UBMT"),
        ("RSMT",  "RSMT"),
        ("RNMT",  "RNMT"),
        ("DBMT",  "DBMT"),
        ("ECNT",  "ECNT"),
        ("RSRP",  "RSRP"),
        ("RSCP",  "RSCP"),
        ("SINR",  "CINR"),
        ("BLER",  "BLER"),
    ]),
    "DROP": OrderedDict([
        ("ACT",         "ACT_"),
        ("LAC",         "LAC_"),
        ("TAC",         "TAC_"),
        ("PCI",         "PhID"),
        ("DLCh",        "DLCh"),
        ("Band",        "LBND"),
        ("RxP0_avg",    "RxP0"),
        ("RxP1_avg",    "RxP1"),
        ("SNR0_avg",    "SNR0"),
        ("BLER_avg",    "BLER"),
        ("RSCP_avg",    "RSCP"),
        ("SIPR",        "SIP값"),
    ]),
    "RLFI": OrderedDict([
        ("ACT",     "ACT1"),
        ("LAC",     "LAC1"),
        ("TAC",     "TAC1"),
        ("PID",     ("PID", "PID1", "PID2", "PID3", "PID4")),
        ("DCh",     "DCh1"),
        ("RxP_avg", "RxP1"),
        ("CAU",     "CAU1"),
    ]),
    "NSVC": OrderedDict([
        ("Date",  "__date__"),
        ("합계",  "CNT_"),
        ("LEV0",  "LEV0"),
        ("LEV1",  "LEV1"),
        ("LEV2",  "LEV2"),
        ("LEV3",  "LEV3"),
        ("LEV4",  "LEV4"),
        ("LEV5",  "LEV5"),
    ]),
    "SCGF": OrderedDict([
        ("PLMN",  "PLMN"),
        ("TAC",   "TAC_"),
        ("PhID",  "PhID"),
        ("Lband", ("LBnd", "MBnd")),
        ("Nband", ("NBnd", "SBnd")),
        ("Ftype", "Ftype"),
    ]),
    "ATTF": OrderedDict([
        ("Feature", "__feature__"),
        ("PLMN",  "PLMN"),
        ("ACT_",  "ACT_"),
        ("LAC_",  "LAC_"),
        ("TAC_",  "TAC_"),
        ("PhID_", "PhID"),
        ("DLCh",  "DLCh"),
        ("EMMC",  "EMMC"),
    ]),
    "ATTI": OrderedDict([
        ("Feature", "__feature__"),
        ("PLMN",  "PLMN"),
        ("ACT_",  "ACT_"),
        ("LAC_",  "LAC_"),
        ("TAC_",  "TAC_"),
        ("PhID_", "PhID"),
        ("DLCh",  "DLCh"),
        ("EMMC",  "EMMC"),
    ]),
    "CRSH": OrderedDict([
        ("PLMN",  "PLMN"),
        ("ACT_",  "ACT_"),
        ("LAC_",  "LAC_"),
        ("TAC_",  "TAC_"),
        ("PhID",  "PhID"),
        ("DLCh",  "DLCh"),
        ("File",  "File"),
        ("Line",  "Line"),
        ("Msg",   "Msg_"),
        ("InCa",  "InCa"),
    ]),
    "CEND": OrderedDict([
        ("ACT",  "ACT_"),
        ("TAC",  "TAC_"),
        ("LAC",  "LAC_"),
        ("PCI",  "PhID"),
        ("DLCh", "DLCh"),
        ("SIPR", "SIP값"),
    ]),
    # 추후 추가: ATTS, SIMD 등
}


# ─── ACT 값 매핑 ─────────────────────────────────────────────────────────────
_ACT_MAP: dict[str, str] = {"2": "3G", "4": "LTE", "6": "5G"}


_STATIC_FOOTNOTES: dict[str, list[str]] = {}

_NSVC_LEV_FOOTNOTES: dict[str, str] = {
    "LEV0": "LEV0: 2분 미만",
    "LEV1": "LEV1: 5분 미만",
    "LEV2": "LEV2: 10분 미만",
    "LEV3": "LEV3: 30분 미만",
    "LEV4": "LEV4: 60분 미만",
    "LEV5": "LEV5: 60분 이상",
}

# ─── feature별 최종 표시 컬럼 (집계 완료 후 이 컬럼만 남김) ─────────────────────
# 순서도 여기서 지정한 순서대로 유지됩니다.
FEATURE_KEEP_COLS: dict[str, list[str]] = {
    "MUTE": ["ACT", "TAC", "PCI", "Band", "ECNT", "RSRP", "SINR", "BLER"],
    "DROP": ["ACT", "TAC", "PCI", "DLCh", "Drop횟수", "RxP0_avg", "RxP1_avg", "BLER_avg", "SIPR_Counts"],
    "RLFI": ["ACT", "TAC", "PID", "DCh", "RLFI횟수", "RxP_avg", "CAU_Counts"],
    "SCGF": ["TAC", "PhID", "Lband", "Nband", "SCGF발생횟수", "Ftype_Counts"],
}

# ─── feature별 컬럼명 변경 (집계 후 표시용 이름으로 변환) ────────────────────────
FEATURE_RENAME_COLS: dict[str, dict[str, str]] = {
    "DROP": {
        "Drop횟수":   "발생횟수",
        "RxP0_avg":   "RxP0",
        "RxP1_avg":   "RxP1",
        "BLER_avg":   "BLER",
        "SIPR_Counts": "SIP값",
    },
    "RLFI": {
        "RLFI횟수":  "발생횟수",
        "RxP_avg":   "RxP",
        "CAU_Counts": "원인",
    },
    "SCGF": {
        "Lband":        "L밴드",
        "Nband":        "N밴드",
        "SCGF발생횟수":  "발생횟수",
        "Ftype_Counts": "원인",
    },
}



HEX_COLUMNS: set[str] = {"TAC", "LAC", "TAC_", "LAC_"}


# ─── feature별 집계 규칙 ──────────────────────────────────────────────────────
# group_by     : 동일 조합으로 묶을 표시명 컬럼 목록
# sum          : 합계를 낼 컬럼
# avg          : 평균을 낼 컬럼 (소수점 1자리)
# first        : 그룹 내 첫 번째 값을 그대로 사용할 컬럼
# drop         : 집계 후 제거할 컬럼
# count_col    : 그룹 행 수를 표시할 새 컬럼명 (group_by 바로 뒤에 삽입)
# value_counts : 고유값별 출현 횟수를 "값:N회" 형식으로 표시할 컬럼명
# sort_by      : 집계 후 내림차순 정렬 기준 컬럼
FEATURE_AGGREGATION: dict[str, dict] = {
    "MUTE": {
        "group_by": ["PLMN", "ACT", "TAC", "LAC", "PCI", "DLCh", "Band"],
        "sum":      ["UBMT", "RSMT", "RNMT", "DBMT", "ECNT"],
        "avg":      ["RSRP", "RSCP", "SINR", "BLER"],
        "first":    ["Band"],
        "drop":     ["Date", "Time"],
        "sort_by":  "ECNT",
    },
    "DROP": {
        "group_by":     ["ACT", "LAC", "TAC", "PCI", "DLCh", "Band"],
        "count_col":    "Drop횟수",
        "avg":          ["RxP0_avg", "RxP1_avg", "SNR0_avg", "BLER_avg", "RSCP_avg"],
        "value_counts": "SIPR",
        "sort_by":      "Drop횟수",
    },
    "RLFI": {
        "group_by":      ["ACT", "LAC", "TAC", "PID", "DCh"],
        "count_col":     "RLFI횟수",
        "count_col_pos": "end",
        "avg":           ["RxP_avg"],
        "value_counts":  "CAU",
        "sort_by":       "RLFI횟수",
    },
    "NSVC": {
        "sort_by":   "Date",
        "sort_asc":  True,
        "row_limit": 50,
    },
    "SCGF": {
        "group_by":      ["PLMN", "TAC", "PhID", "Lband", "Nband"],
        "count_col":     "SCGF발생횟수",
        "count_col_pos": "end",
        "value_counts":  "Ftype",
        "sort_by":       "SCGF발생횟수",
    },
    "ATTF": {
        "group_by":      ["Feature", "PLMN", "ACT_", "LAC_", "TAC_", "PhID_", "DLCh"],
        "count_col":     "Count",
        "value_counts":  "EMMC",
        "sort_by":       "Count",
    },
    "ATTI": {
        "group_by":      ["Feature", "PLMN", "ACT_", "LAC_", "TAC_", "PhID_", "DLCh"],
        "count_col":     "Count",
        "value_counts":  "EMMC",
        "sort_by":       "Count",
    },
    "CRSH": {
        "group_by":      ["PLMN", "ACT_", "LAC_", "TAC_", "PhID", "DLCh"],
        "count_col":     "Count",
        "count_col_pos": "end",
        "value_counts":  "InCa",
        "sort_by":       "Count",
    },
    "CEND": {
        "group_by":      ["ACT", "TAC", "LAC", "PCI", "DLCh"],
        "count_col":     "CEND Count",
        "value_counts":  "SIPR",
        "sort_by":       "CEND Count",
    },
}


# ─── 데이터 클래스 ────────────────────────────────────────────────────────────

@dataclass
class FeatureTable:
    feature: str
    columns: list[str]
    rows: list[list[str]]
    footnotes: list[str] = field(default_factory=list)
    label: str = ""        # 표시 제목 (없으면 feature 사용)
    total_count: int = 0   # row_limit 적용 전 전체 행 수 (0이면 len(rows) 그대로 표시)
    count_label: str = ""  # 건수 자리에 표시할 커스텀 문자열 (설정 시 자동 건수 대신 사용)

    def to_text(self) -> str:
        """AI Agent 전송용 plain-text 테이블 (전체 행, 가로 형식).

        AI가 모든 데이터를 분석할 수 있도록 전체 행을 가로 형식으로 전달합니다.
        챗봇 표시 시 _md_table_to_vertical()에서 세로로 변환합니다.
        """
        if not self.rows:
            return f"[{self.feature}] 데이터 없음"

        n_total = len(self.rows)
        header_label = f"[{self.feature}] {n_total}건"

        if self.feature == "MUTE_EXTRA":
            row = self.rows[0]
            pairs = "  ".join(f"{c}:{row[i]}" for i, c in enumerate(self.columns))
            return f"{header_label}\n{pairs}"

        col_header = " | ".join(self.columns)
        sep = "-" * max(len(col_header), 20)
        data_lines = [" | ".join(str(v) for v in row) for row in self.rows]
        lines = [header_label, col_header, sep] + data_lines
        if self.footnotes:
            lines += ["", "※ " + " / ".join(self.footnotes)]
        return "\n".join(lines)

    def to_html(self) -> str:
        """챗봇 표시용 HTML 테이블"""
        if not self.rows:
            display_title = self.label or self.feature
            return (
                f'<div class="feat-table-wrap">'
                f'<div class="feat-label">{display_title}</div>'
                f'<p class="no-data">데이터 없음</p></div>'
            )
        th = "".join(f"<th>{c}</th>" for c in self.columns)
        tbody = "".join(
            "<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>"
            for row in self.rows
        )
        footnote_html = ""
        if self.footnotes:
            text = " / ".join(self.footnotes)
            footnote_html = f'<p class="feat-footnote">※ {text}</p>'
        display_title = self.label or self.feature
        if self.count_label:
            count_str = self.count_label
        elif self.total_count and self.total_count > len(self.rows):
            count_str = f"상위 {len(self.rows)}건 / 전체 {self.total_count}건"
        else:
            count_str = f"{len(self.rows)}건"
        return (
            f'<div class="feat-table-wrap">'
            f'<div class="feat-label">{display_title}'
            f' <span class="feat-count">({count_str})</span></div>'
            f'<div class="tbl-scroll"><table>'
            f'<thead><tr>{th}</tr></thead>'
            f'<tbody>{tbody}</tbody>'
            f'</table></div>'
            f'{footnote_html}'
            f'</div>'
        )


@dataclass
class ProcessedData:
    sn: str
    summary_text: str       # AI Agent 전송 데이터 텍스트 (TextInput-n8kcD)
    feature_tables: dict[str, FeatureTable] = field(default_factory=dict)
    html_tables: str = ""   # 챗봇 HTML 렌더링용
    error: str | None = None
    plmn: str = ""          # 원시 데이터에서 추출한 PLMN (사업자 판단용)
    device_model: str = ""  # 단말 모델명

    # main.py 기존 코드 호환 (processed.device.*)
    @property
    def device(self):
        return _CompatDevice(self.sn)


class _CompatDevice:
    """main.py의 processed.device.* 접근 호환용 더미"""
    def __init__(self, sn: str):
        self.sn = sn
        self.model = ""
        self.status = ""
        self.customer_name = ""
        self.contract_active = False
        self.service_history: list = []


def _safe_float(v: str) -> float:
    """정렬용 숫자 변환 헬퍼. 변환 불가 시 -inf 반환."""
    try:
        return float(v)
    except (ValueError, TypeError):
        return float("-inf")


# ─── 메인 프로세서 ────────────────────────────────────────────────────────────

class DataProcessor:
    """CSV 데이터를 feature별 테이블로 가공합니다."""

    def process(self, query_result: QueryResult) -> ProcessedData:
        if not query_result.success:
            return ProcessedData(
                sn=query_result.sn,
                summary_text="",
                error=query_result.error,
            )

        # rows 가 비어 있으면 csv_path 에서 직접 읽기
        rows: list[dict] = list(query_result.rows)
        if not rows and query_result.csv_path:
            rows = self._read_csv(query_result.csv_path)

        if not rows:
            return ProcessedData(
                sn=query_result.sn,
                summary_text=f"SN '{query_result.sn}'의 조회 결과가 없습니다.",
                error="데이터 없음",
            )

        rows = self._fill_mute_pci_from_cend(rows)

        # keep_cols 필터 전에 PLMN 추출 (사업자 판단용)
        plmn = ""
        for row in rows:
            cv_raw = row.get("custom_value", "{}")
            try:
                cv = json.loads(cv_raw) if isinstance(cv_raw, str) else cv_raw
                plmn = str(cv.get("PLMN", "")).rstrip("#").strip()
            except Exception:
                pass
            if plmn:
                break

        # 단말 모델명 추출 (첫 번째 row의 device_model 컬럼)
        _dm = str(rows[0].get("device_model", "") or "").strip()
        device_model = "" if _dm.lower() in ("none", "null", "nan") else _dm
        logger.info(f"단말정보 - device_model: '{device_model}', PLMN: '{plmn}'")

        feature_tables = self._build_feature_tables(rows, apply_keep_cols=True)
        from app.config import settings as _settings
        if _settings.AI_AGENT_INPUT_FORMAT == "narrative":
            full_tables = self._build_feature_tables(rows, apply_keep_cols=False)
            summary = self._build_summary_narrative(query_result.sn, rows, full_tables)
        else:
            summary = self._build_summary(query_result.sn, rows, feature_tables)

        # 단말정보 헤더 HTML (Feature 테이블 위에 표시)
        _PLMN_DISPLAY = {
            "45005": "SKT",
            "45008": "KT",  "45002": "KT", "45004": "KT",
            "45006": "LGU+","45018": "LGU+", "45010": "LGU+",
        }
        operator_display = _PLMN_DISPLAY.get(plmn, plmn or "-")
        logger.info(f"사업자 표시: PLMN={plmn!r} → {operator_display!r}")
        query_days = _settings.QUERY_LOOKBACK_DAYS
        device_header = (
            f'<div class="device-info-bar">'
            f'<span><b>SN</b>&nbsp;{query_result.sn}</span>'
            f'<span><b>사업자</b>&nbsp;{operator_display}</span>'
            f'<span><b>모델</b>&nbsp;{device_model or "-"}</span>'
            f'<span class="query-period">최근 {query_days}일간의 데이터</span>'
            f'</div>'
        )
        html_tables = device_header + "".join(t.to_html() for t in feature_tables.values())

        logger.info(
            f"데이터 가공 완료 - SN: {query_result.sn}, "
            f"features: {list(feature_tables.keys())}, 총 {len(rows)}건"
        )

        return ProcessedData(
            sn=query_result.sn,
            summary_text=summary,
            feature_tables=feature_tables,
            html_tables=html_tables,
            plmn=plmn,
            device_model=device_model,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────────────────

    def _build_feature_tables(self, rows: list[dict], apply_keep_cols: bool = True) -> dict[str, FeatureTable]:
        """feature별로 그룹화하고 FeatureTable 목록을 반환합니다."""
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            feat = str(row.get("feature", "")).strip().upper()
            if feat:
                grouped.setdefault(feat, []).append(row)

        logger.info(f"CSV 내 feature 목록: {list(grouped.keys())} (총 {len(grouped)}종류)")

        tables: dict[str, FeatureTable] = {}
        for feat, feat_rows in grouped.items():
            col_map = FEATURE_COLUMNS.get(feat)
            logger.info(f"feature '{feat}': {len(feat_rows)}건, 매핑 {'있음' if col_map else '없음(raw출력)'}")
            if col_map:
                table_rows = []
                for row in feat_rows:
                    cv = self._parse_custom_value(str(row.get("custom_value", "") or ""))
                    tr = []
                    for col_name, json_key in col_map.items():
                        if json_key == "__date__":
                            val = str(row.get("Date", "") or "")
                        elif json_key == "__time__":
                            val = str(row.get("Time", "") or "")
                        elif json_key == "__feature__":
                            val = feat
                        else:
                            if isinstance(json_key, tuple):
                                val = next((cv[k] for k in json_key if cv.get(k)), "")
                            else:
                                val = cv.get(json_key, "")
                            if col_name in HEX_COLUMNS:
                                val = self._hex_to_dec(val)
                            if col_name == "ACT":
                                val = _ACT_MAP.get(val.strip(), val)
                        tr.append(val)
                    table_rows.append(tr)

                columns = list(col_map.keys())

                # MUTE: ECNT 없는 행은 집계에서 제외
                if feat == "MUTE" and "ECNT" in columns:
                    ecnt_idx = columns.index("ECNT")
                    orig_count = len(table_rows)
                    table_rows = [r for r in table_rows if r[ecnt_idx].strip() and r[ecnt_idx].strip() != "0"]
                    excluded = orig_count - len(table_rows)
                    if excluded:
                        logger.info(f"[MUTE] ECNT 없는 행 {excluded}건 제외 (집계 대상: {len(table_rows)}건)")

                columns, agg_rows, footnotes = self._aggregate_rows(feat, columns, table_rows)

                # drop 컬럼 제거
                drop_cols = set(FEATURE_AGGREGATION.get(feat, {}).get("drop", []))
                if drop_cols:
                    keep_idx = [i for i, c in enumerate(columns) if c not in drop_cols]
                    columns  = [columns[i] for i in keep_idx]
                    agg_rows = [[row[i] for i in keep_idx] for row in agg_rows]

                # 정렬 (sort_asc=True면 오름차순, 기본 내림차순)
                sort_col = FEATURE_AGGREGATION.get(feat, {}).get("sort_by")
                sort_asc = FEATURE_AGGREGATION.get(feat, {}).get("sort_asc", False)
                if sort_col and sort_col in columns:
                    si = columns.index(sort_col)
                    if sort_col == "Date":
                        agg_rows.sort(key=lambda r: r[si], reverse=not sort_asc)
                    else:
                        agg_rows.sort(key=lambda r: _safe_float(r[si]), reverse=not sort_asc)

                # 행 수 제한 (feature별 row_limit, 기본 10)
                total_count = len(agg_rows)
                row_limit = FEATURE_AGGREGATION.get(feat, {}).get("row_limit", 10)
                agg_rows = agg_rows[:row_limit]

                # 표시 컬럼 필터 (FEATURE_KEEP_COLS 지정 시 해당 컬럼만, 순서 유지)
                # apply_keep_cols=False 이면 모든 컬럼 유지 (서술형 AI 입력용)
                if apply_keep_cols:
                    keep = FEATURE_KEEP_COLS.get(feat)
                    if keep:
                        keep_idx = [i for i, c in enumerate(columns) if c in keep]
                        keep_idx.sort(key=lambda i: keep.index(columns[i]))
                        columns  = [columns[i] for i in keep_idx]
                        agg_rows = [[row[i] for i in keep_idx] for row in agg_rows]

                # 컬럼명 변경 (FEATURE_RENAME_COLS)
                rename = FEATURE_RENAME_COLS.get(feat)
                if rename:
                    columns = [rename.get(c, c) for c in columns]

                # NSVC: Date 연도 제거(MM-DD만 표시) + 값 있는 LEV만 주석 표시
                if feat == "NSVC" and agg_rows:
                    col_idx = {c: i for i, c in enumerate(columns)}
                    if "Date" in col_idx:
                        di = col_idx["Date"]
                        for r in agg_rows:
                            d = r[di]
                            # YYYY-MM-DD → MM-DD
                            if d and len(d) >= 10 and d[4] == "-":
                                r[di] = d[5:]
                    active_levs = set()
                    for r in agg_rows:
                        for col in _NSVC_LEV_FOOTNOTES:
                            if col in col_idx and r[col_idx[col]] not in ("", "0", None):
                                active_levs.add(col)
                    nsvc_notes = [
                        note for col, note in _NSVC_LEV_FOOTNOTES.items()
                        if col in active_levs
                    ]
                    footnotes = footnotes + nsvc_notes

                tables[feat] = FeatureTable(
                    feature=feat,
                    columns=columns,
                    rows=agg_rows,
                    footnotes=footnotes + _STATIC_FOOTNOTES.get(feat, []),
                    total_count=total_count,
                    count_label="" ,
                )

                # DROP: 개별 발생 행 테이블 (날짜/TAC/PCI, 날짜순)
                if feat == "DROP":
                    raw_rows = []
                    for raw_row in feat_rows:
                        cv = self._parse_custom_value(str(raw_row.get("custom_value", "") or ""))
                        date_val = str(raw_row.get("Date", "") or "")
                        if date_val and len(date_val) >= 10 and date_val[4] == "-":
                            date_val = date_val[5:]   # YYYY-MM-DD → MM-DD
                        tac_val  = self._hex_to_dec(str(cv.get("TAC_", "") or ""))
                        pci_val  = str(cv.get("PhID", "") or "")
                        raw_rows.append([date_val, tac_val, pci_val])
                    raw_rows.sort(key=lambda r: r[0])
                    tables["DROP_RAW"] = FeatureTable(
                        feature="DROP_RAW",
                        label="Drop 발생현황",
                        columns=["날짜", "TAC", "PCI"],
                        rows=raw_rows,
                    )

            else:
                # 매핑 미정의 feature: Date / Time / custom_value 축약 표시
                table_rows = [
                    [
                        str(r.get("Date", "")),
                        str(r.get("Time", "")),
                        str(r.get("custom_value", ""))[:120],
                    ]
                    for r in feat_rows
                ]
                tables[feat] = FeatureTable(
                    feature=feat,
                    columns=["Date", "Time", "custom_value (축약)"],
                    rows=table_rows,
                )

        # MUTE 보조 테이블: SAMS / SMBU / MCST 전체 value_counts
        if "MUTE" in grouped:
            extra_cols = ["SAMS", "SMBU", "MCST"]
            vc: dict[str, dict[str, int]] = {c: {} for c in extra_cols}
            for row in grouped["MUTE"]:
                cv = self._parse_custom_value(str(row.get("custom_value", "") or ""))
                for col in extra_cols:
                    v = str(cv.get(col, "")).strip()
                    if v:
                        vc[col][v] = vc[col].get(v, 0) + 1
            # 하나라도 값이 있는 경우에만 테이블 추가
            if any(vc[c] for c in extra_cols):
                footnote_map: dict[str, str] = {}
                summary_row = []
                for c in extra_cols:
                    if vc[c]:
                        parts = []
                        for v, n in sorted(vc[c].items(), key=lambda x: -x[1]):
                            full = apply_code(c, v)
                            if "(" in full and full.endswith(")"):
                                code = full[:full.index("(")]
                                desc = full[full.index("(")+1:-1]
                                footnote_map[code] = desc
                                parts.append(f"{code}:{n}회")
                            else:
                                parts.append(f"{full}:{n}회")
                        summary_row.append(", ".join(parts))
                    else:
                        summary_row.append("-")
                footnotes = [f"{code}: {desc}" for code, desc in sorted(footnote_map.items())]
                tables["MUTE_EXTRA"] = FeatureTable(
                    feature="MUTE(SAMS/SMBU/MCST)",
                    columns=extra_cols,
                    rows=[summary_row],
                    footnotes=footnotes,
                )
                logger.debug(f"MUTE 보조 테이블 생성: {summary_row}")

        return tables

    def _fill_mute_pci_from_cend(self, rows: list[dict]) -> list[dict]:
        """MUTE에서 PhID(PCI)가 없을 때 ±5초 내 같은 TAC의 CEND PhID로 채웁니다."""
        from datetime import datetime, timedelta

        def parse_dt(row: dict) -> datetime | None:
            try:
                d = str(row.get("Date", "")).strip()
                t = str(row.get("Time", "")).strip()
                return datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M:%S")
            except Exception:
                return None

        # CEND 행만 미리 파싱
        cend_rows: list[tuple[datetime, dict, dict]] = []
        for row in rows:
            feat = str(row.get("feature", "")).strip().upper()
            if feat != "CEND":
                continue
            dt = parse_dt(row)
            if dt is None:
                continue
            cv = self._parse_custom_value(str(row.get("custom_value", "") or ""))
            phid = str(cv.get("PhID", "")).strip()
            tac  = str(cv.get("TAC_", "")).strip()
            if phid and tac:
                cend_rows.append((dt, {"PhID": phid, "TAC_": tac}, row))

        if not cend_rows:
            return rows

        filled = 0
        window = timedelta(seconds=5)
        result = []
        for row in rows:
            feat = str(row.get("feature", "")).strip().upper()
            if feat != "MUTE":
                result.append(row)
                continue

            cv = self._parse_custom_value(str(row.get("custom_value", "") or ""))
            if cv.get("PhID", "").strip():
                result.append(row)
                continue

            # ECNT 없으면 CEND PCI 보완 대상 아님 (어차피 집계에서 제외됨)
            ecnt = str(cv.get("ECNT", "")).strip()
            if not ecnt or ecnt == "0":
                result.append(row)
                continue

            dt = parse_dt(row)
            mute_tac = str(cv.get("TAC_", "")).strip()
            if dt is None or not mute_tac:
                result.append(row)
                continue

            # ±5초 내 같은 TAC CEND 중 가장 가까운 것
            best_phid = None
            best_diff = None
            for cend_dt, cend_cv, _ in cend_rows:
                if abs(cend_dt - dt) > window:
                    continue
                if cend_cv["TAC_"] != mute_tac:
                    continue
                diff = abs((cend_dt - dt).total_seconds())
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    best_phid = cend_cv["PhID"]

            if best_phid:
                import json as _json
                cv["PhID"] = best_phid
                try:
                    row = dict(row)
                    row["custom_value"] = _json.dumps(cv, ensure_ascii=False)
                    filled += 1
                except Exception:
                    pass

            result.append(row)

        if filled:
            logger.info(f"[MUTE PCI 보완] {filled}건 CEND PhID로 채움")
        return result

    def _aggregate_rows(
        self,
        feat: str,
        columns: list[str],
        rows: list[list[str]],
    ) -> tuple[list[str], list[list[str]], list[str]]:
        """FEATURE_AGGREGATION 규칙에 따라 행을 그룹화·집계합니다.
        (columns, rows, footnotes) 튜플을 반환합니다."""
        agg_cfg = FEATURE_AGGREGATION.get(feat)
        if not agg_cfg or not rows:
            return columns, rows, []

        col_idx = {c: i for i, c in enumerate(columns)}
        raw_group_by   = agg_cfg.get("group_by", None)
        aggregate_all  = raw_group_by == []          # 빈 리스트 = 전체를 하나로 집계
        group_by_cols  = [c for c in (raw_group_by or []) if c in col_idx]
        sum_cols       = [c for c in agg_cfg.get("sum",  []) if c in col_idx]
        avg_cols       = [c for c in agg_cfg.get("avg",  []) if c in col_idx]
        count_col      = agg_cfg.get("count_col")   # 그룹 행 수 컬럼명
        vc_col         = agg_cfg.get("value_counts") # 고유값 카운트 컬럼명
        footnote_map: dict[str, str] = {}            # code → description (주석용)

        if not group_by_cols and not aggregate_all:
            return columns, rows, []

        # 그룹 키 → 해당 rows 묶기
        groups: dict[tuple, list[list[str]]] = {}
        if aggregate_all:
            groups[("__all__",)] = rows
        else:
            for row in rows:
                key = tuple(row[col_idx[c]] for c in group_by_cols)
                groups.setdefault(key, []).append(row)

        result = []
        for group_rows in groups.values():
            merged = list(group_rows[0])

            # Date: min ~ max 범위
            if "Date" in col_idx:
                dates = [r[col_idx["Date"]] for r in group_rows if r[col_idx["Date"]]]
                if dates:
                    mn, mx = min(dates), max(dates)
                    merged[col_idx["Date"]] = f"{mn}~{mx}" if mn != mx else mn

            # 합계 컬럼
            for col in sum_cols:
                total = 0
                for r in group_rows:
                    try:
                        total += int(float(r[col_idx[col]] or 0))
                    except (ValueError, TypeError):
                        pass
                merged[col_idx[col]] = str(total)

            # 평균 컬럼 (LEV 컬럼은 정수, 나머지는 소수점 1자리)
            for col in avg_cols:
                vals = []
                for r in group_rows:
                    try:
                        v = r[col_idx[col]]
                        if v:
                            vals.append(float(v))
                    except (ValueError, TypeError):
                        pass
                if vals:
                    avg = sum(vals) / len(vals)
                    merged[col_idx[col]] = f"{int(round(avg))}" if col.startswith("LEV") else f"{avg:.1f}"
                else:
                    merged[col_idx[col]] = ""

            # 고유값 카운트 (표: "487:2회" / 주석: "487: requested_terminated")
            if vc_col and vc_col in col_idx:
                vc_counts: dict[str, int] = {}
                for r in group_rows:
                    v = r[col_idx[vc_col]].strip()
                    if v:
                        vc_counts[v] = vc_counts.get(v, 0) + 1
                cell_parts = []
                for v, n in sorted(vc_counts.items(), key=lambda x: -x[1]):
                    full = apply_code(vc_col, v)
                    if "(" in full and full.endswith(")"):
                        code = full[:full.index("(")]
                        desc = full[full.index("(")+1:-1]
                        footnote_map[code] = desc
                        cell_parts.append(f"{code}:{n}회")
                    else:
                        cell_parts.append(f"{full}:{n}회")
                merged[col_idx[vc_col]] = ", ".join(cell_parts)

            result.append(merged)

        # count_col 삽입: "start"=맨 앞, "end"=맨 뒤, 기본=group_by 바로 뒤
        if count_col:
            pos = agg_cfg.get("count_col_pos")
            if pos == "start":
                insert_pos = 0
            elif pos == "end":
                insert_pos = len(columns)
            else:
                insert_pos = len(group_by_cols)
            columns = columns[:insert_pos] + [count_col] + columns[insert_pos:]
            group_sizes = [len(g) for g in groups.values()]
            result = [
                row[:insert_pos] + [str(sz)] + row[insert_pos:]
                for row, sz in zip(result, group_sizes)
            ]

        # value_counts 컬럼명 변경 (SIPR → SIPR_Counts)
        if vc_col and vc_col in columns:
            columns = [f"{vc_col}_Counts" if c == vc_col else c for c in columns]

        footnotes = [f"{code}: {desc}" for code, desc in sorted(footnote_map.items())]
        logger.debug(
            f"[{feat}] 집계 완료: 원본 {len(rows)}건 → 집계 {len(result)}건 "
            f"(group_by={group_by_cols})"
        )
        return columns, result, footnotes

    def _build_summary(
        self,
        sn: str,
        rows: list[dict],
        feature_tables: dict[str, FeatureTable],
    ) -> str:
        """AI Agent 전송용 텍스트 요약을 생성합니다."""
        # AI에 전송할 feature (집계 정리된 테이블만, CEND 등 raw 제외)
        _AI_FEATURES = {"MUTE", "DROP", "RLFI", "SCGF", "NSVC", "ATTF", "CRSH", "MUTE_EXTRA"}

        lines: list[str] = []

        # ─ Feature별 원본 행 수 (건수 내림차순 Top 7) ─────────────────────────
        feat_dist: dict[str, int] = {}
        for r in rows:
            f = str(r.get("feature", "")).strip().upper()
            if f:
                feat_dist[f] = feat_dist.get(f, 0) + 1
        top_feats = sorted(feat_dist.items(), key=lambda x: x[1], reverse=True)[:10]
        feat_summary = ", ".join(f"{f} {n}건" for f, n in top_feats)

        lines.append(f"[단말기 SN: {sn}]")
        lines.append(f"Feature 분포: {feat_summary or '없음'}")
        lines.append("")

        # ─ 집계된 feature 테이블만 출력 (raw 데이터 제외) ─────────────────────
        for feat_name, table in feature_tables.items():
            if feat_name.upper() not in _AI_FEATURES:
                continue
            # MUTE_EXTRA는 전체, 나머지는 상위 2행만
            if feat_name.upper() == "MUTE_EXTRA":
                lines.append(table.to_text())
            else:
                sliced = FeatureTable(
                    feature=table.feature,
                    columns=table.columns,
                    rows=table.rows[:3],
                    footnotes=table.footnotes,
                )
                lines.append(sliced.to_text())
            lines.append("")

        return "\n".join(lines)

    def _build_summary_narrative(
        self,
        sn: str,
        rows: list[dict],
        feature_tables: dict[str, FeatureTable],
    ) -> str:
        """AI Agent 전송용 서술형 텍스트 요약을 생성합니다."""
        _ORDINALS = ["제일", "두번째로", "세번째로"]

        def _col(tbl: FeatureTable, row: list, name: str) -> str:
            return row[tbl.columns.index(name)] if name in tbl.columns else ""

        def _decode_cell(field: str, cell: str) -> str:
            """'1:2회, 5:1회' 형태 셀에서 주요 코드를 추출해 설명을 붙여 반환합니다.
            예: _decode_cell("SIPR", "1:2회") → "1(max transmission)"
            """
            if not cell:
                return cell
            first = cell.split(",")[0].strip()
            code = first.split(":")[0].strip() if ":" in first else first
            return apply_code(field, code)

        # ─ Feature 분포 ───────────────────────────────────────────────────────
        feat_dist: dict[str, int] = {}
        for r in rows:
            f = str(r.get("feature", "")).strip().upper()
            if f:
                feat_dist[f] = feat_dist.get(f, 0) + 1
        top_feats = sorted(feat_dist.items(), key=lambda x: x[1], reverse=True)[:10]
        feat_summary = " ".join(f"{f}({n}회)" for f, n in top_feats)

        lines: list[str] = []
        lines.append(f"[단말기 SN: {sn}]")
        lines.append(f"Feature가 많이 발생한 순서는 {feat_summary} 순입니다.")
        lines.append("")

        def _tag_weak_field(rsrp_str: str, sinr_str: str, bler_str: str) -> str:
            """RSRP/SINR/BLER 기준으로 전계 점검 필요 여부 판단."""
            flags = []
            try:
                if float(rsrp_str) < -100:
                    flags.append("RSRP 약전계")
            except (ValueError, TypeError):
                pass
            try:
                if float(sinr_str) < 0:
                    flags.append("SINR 불량")
            except (ValueError, TypeError):
                pass
            try:
                if float(bler_str) >= 30:
                    flags.append("BLER 높음")
            except (ValueError, TypeError):
                pass
            if flags:
                return f"⚠️ 전계 점검 필요({', '.join(flags)})"
            return ""

        def _safe_int(v: str) -> int:
            try:
                return int(float(v)) if v else 0
            except (ValueError, TypeError):
                return 0

        # ─ MUTE ──────────────────────────────────────────────────────────────
        mute = feature_tables.get("MUTE")
        if mute and mute.rows:
            # UBMT 비율 계산 (전체 rows 합산)
            total_ubmt = sum(_safe_int(_col(mute, r, "UBMT")) for r in mute.rows)
            total_mute_cnt = sum(
                _safe_int(_col(mute, r, c))
                for r in mute.rows
                for c in ["UBMT", "RSMT", "RNMT", "DBMT"]
            )
            ubmt_ratio = (total_ubmt / total_mute_cnt * 100) if total_mute_cnt > 0 else 0

            for i, row in enumerate(mute.rows[:3]):
                ord_ = _ORDINALS[i] if i < len(_ORDINALS) else f"{i+1}번째로"
                tac  = _col(mute, row, "TAC")
                pci  = _col(mute, row, "PCI")
                band = _col(mute, row, "Band")
                ubmt = _col(mute, row, "UBMT")
                rsmt = _col(mute, row, "RSMT")
                rnmt = _col(mute, row, "RNMT")
                dbmt = _col(mute, row, "DBMT")
                ecnt = _col(mute, row, "ECNT")
                rsrp = _col(mute, row, "RSRP")
                sinr = _col(mute, row, "SINR")
                bler = _col(mute, row, "BLER")
                cnt_str = ""
                if ubmt: cnt_str += f" UBMT {ubmt}회"
                if rsmt: cnt_str += f" RSMT {rsmt}회"
                if rnmt: cnt_str += f" RNMT {rnmt}회"
                if dbmt: cnt_str += f" DBMT {dbmt}회"
                if ecnt: cnt_str += f" ECNT {ecnt}번"
                weak_field = _tag_weak_field(rsrp, sinr, bler)
                weak_str = f" {weak_field}" if weak_field else ""
                lines.append(
                    f"MUTE가 {ord_} 많이 발생한 지역은 TAC {tac} PCI {pci} Band{band}이고"
                    f"{cnt_str} 발생하였고, RSRP는 {rsrp}, SINR {sinr} BLER {bler}입니다.{weak_str}"
                )
            if ubmt_ratio >= 30:
                top_row  = mute.rows[0]
                top_tac  = _col(mute, top_row, "TAC")
                top_pci  = _col(mute, top_row, "PCI")
                top_band = _col(mute, top_row, "Band")
                loc_str  = f" (주요 발생지: TAC {top_tac} PCI {top_pci} Band{top_band})" if top_tac else ""
                lines.append(
                    f"⚠️ UBMT 비율 {ubmt_ratio:.0f}% ({total_ubmt}/{total_mute_cnt}회) → 송신 이슈 가능성{loc_str}"
                )
            lines.append("")

        # ─ DROP ──────────────────────────────────────────────────────────────
        drop = feature_tables.get("DROP")
        if drop and drop.rows:
            for i, row in enumerate(drop.rows[:3]):
                ord_ = _ORDINALS[i] if i < len(_ORDINALS) else f"{i+1}번째로"
                tac  = _col(drop, row, "TAC")
                pci  = _col(drop, row, "PCI")
                dlch = _col(drop, row, "DLCh")
                cnt  = _col(drop, row, "Drop횟수") or _col(drop, row, "발생횟수")
                rxp0 = _col(drop, row, "RxP0_avg") or _col(drop, row, "RxP0")
                rxp1 = _col(drop, row, "RxP1_avg") or _col(drop, row, "RxP1")
                snr  = _col(drop, row, "SNR0_avg")
                sipr_raw = _col(drop, row, "SIPR_Counts") or _col(drop, row, "SIPR")
                sipr_code = sipr_raw.split(":")[0].strip() if sipr_raw else ""
                sipr = _decode_cell("SIPR", sipr_raw)
                bler_drop = _col(drop, row, "BLER_avg") or _col(drop, row, "BLER")
                snr_str = f" SNR평균은 {snr}이고" if snr else ""
                sipr_str = f" SIP값은 {sipr}입니다." if sipr else "."
                try:
                    rf_dif_str = " RF Dif가 있습니다." if abs(float(rxp0) - float(rxp1)) >= 7 else ""
                except (ValueError, TypeError):
                    rf_dif_str = ""
                try:
                    repeater_str = (
                        " ⚠️ 중계기 이슈 가능성(BLER 높음 + SIP 1401)"
                        if float(bler_drop) >= 80 and sipr_code == "1401" else ""
                    )
                except (ValueError, TypeError):
                    repeater_str = ""
                lines.append(
                    f"Drop이 {ord_} 많이 발생한 지역은 TAC {tac} PCI {pci} DLCh {dlch}이고"
                    f" Drop횟수는 {cnt}번 RxP0는 {rxp0}, RxP1은 {rxp1},{snr_str}{sipr_str}{rf_dif_str}{repeater_str}"
                )
            lines.append("")

        # ─ RLFI ──────────────────────────────────────────────────────────────
        rlfi = feature_tables.get("RLFI")
        if rlfi and rlfi.rows:
            for i, row in enumerate(rlfi.rows[:3]):
                ord_ = _ORDINALS[i] if i < len(_ORDINALS) else f"{i+1}번째로"
                tac  = _col(rlfi, row, "TAC") or _col(rlfi, row, "TAC1")
                pid  = _col(rlfi, row, "PID")
                dch  = _col(rlfi, row, "DCh") or _col(rlfi, row, "DCh1")
                cnt  = _col(rlfi, row, "RLFI횟수") or _col(rlfi, row, "발생횟수")
                rxp  = _col(rlfi, row, "RxP_avg") or _col(rlfi, row, "RxP")
                cau  = _decode_cell("CAU", _col(rlfi, row, "CAU_Counts") or _col(rlfi, row, "원인"))
                cau_str = f" 원인은 {cau}로" if cau else ""
                lines.append(
                    f"RLFI가 {ord_} 많이 발생한 지역은 TAC {tac} PID {pid} DCh {dch}"
                    f" RxP는 {rxp},{cau_str} 총 {cnt}번 발생하였습니다."
                )
            lines.append("")

        # ─ SCGF ──────────────────────────────────────────────────────────────
        scgf = feature_tables.get("SCGF")
        if scgf and scgf.rows:
            for i, row in enumerate(scgf.rows[:3]):
                ord_ = _ORDINALS[i] if i < len(_ORDINALS) else f"{i+1}번째로"
                tac   = _col(scgf, row, "TAC")
                pci   = _col(scgf, row, "PhID")
                lband = _col(scgf, row, "Lband") or _col(scgf, row, "L밴드")
                nband = _col(scgf, row, "Nband") or _col(scgf, row, "N밴드")
                cnt   = _col(scgf, row, "SCGF발생횟수") or _col(scgf, row, "발생횟수")
                ftype = _col(scgf, row, "Ftype_Counts") or _col(scgf, row, "원인")
                band_str = " ".join(b for b in [lband, nband] if b)
                ftype_str = f" 원인은 {ftype}입니다." if ftype else "입니다."
                lines.append(
                    f"SCGF가 {ord_} 많이 발생한 지역은 TAC {tac} PCI {pci} {band_str}이고"
                    f" 총 {cnt}번 발생하였습니다.{ftype_str}"
                )
            lines.append("")

        # ─ NSVC ──────────────────────────────────────────────────────────────
        nsvc = feature_tables.get("NSVC")
        if nsvc and nsvc.rows:
            lev_cols = [c for c in nsvc.columns if c.startswith("LEV")]
            # 전체 rows 기준으로 판단 (상위 5개 제한 전 full_tables 사용)
            all_nsvc = feature_tables.get("NSVC")
            unique_dates = set(
                _col(nsvc, r, "Date") for r in nsvc.rows
                if _col(nsvc, r, "Date")
            )
            has_lev3 = any(
                _col(nsvc, r, lev) not in ("", "0", None)
                for r in nsvc.rows
                for lev in ("LEV3", "LEV4", "LEV5")
            )
            for row in nsvc.rows:
                date  = _col(nsvc, row, "Date")
                total = _col(nsvc, row, "합계")
                lev_parts = [
                    f"{c} {_col(nsvc, row, c)}"
                    for c in lev_cols
                    if _col(nsvc, row, c) not in ("", "0", None)
                ]
                lev_str = ", ".join(lev_parts)
                date_str = f"{date} " if date else ""
                lines.append(
                    f"NSVC {date_str}합계 {total}회" + (f" ({lev_str})" if lev_str else "") + "."
                )
            if len(unique_dates) >= 3 or has_lev3:
                reasons = []
                if len(unique_dates) >= 3:
                    reasons.append(f"{len(unique_dates)}일간 지속 발생")
                if has_lev3:
                    reasons.append("LEV3 이상 발생")
                lines.append(f"⚠️ NSVC {', '.join(reasons)} → 환경 또는 단말 점검 필요")
            lines.append("")

        # ─ ATTF / ATTI ───────────────────────────────────────────────────────
        for feat_key, label in [("ATTF", "접속실패(ATTF)"), ("ATTI", "접속지연(ATTI)")]:
            tbl = feature_tables.get(feat_key)
            if tbl and tbl.rows:
                for i, row in enumerate(tbl.rows[:3]):
                    ord_ = _ORDINALS[i] if i < len(_ORDINALS) else f"{i+1}번째로"
                    tac  = _col(tbl, row, "TAC_")
                    pci  = _col(tbl, row, "PhID_")
                    cnt  = _col(tbl, row, "Count")
                    emmc = _decode_cell("EMMC", _col(tbl, row, "EMMC_Counts") or _col(tbl, row, "EMMC"))
                    emmc_str = f" 원인은 {emmc}입니다." if emmc else "입니다."
                    lines.append(
                        f"{label}가 {ord_} 많이 발생한 지역은 TAC {tac} PCI {pci}이고"
                        f" {cnt}번 발생하였습니다.{emmc_str}"
                    )
                lines.append("")

        # ─ CRSH ──────────────────────────────────────────────────────────────
        crsh = feature_tables.get("CRSH")
        if crsh and crsh.rows:
            for i, row in enumerate(crsh.rows[:3]):
                ord_ = _ORDINALS[i] if i < len(_ORDINALS) else f"{i+1}번째로"
                tac  = _col(crsh, row, "TAC_")
                pci  = _col(crsh, row, "PhID")
                cnt  = _col(crsh, row, "Count")
                inca = _col(crsh, row, "InCa_Counts") or _col(crsh, row, "InCa")
                inca_str = f" 원인은 {inca}입니다." if inca else "입니다."
                lines.append(
                    f"CRSH가 {ord_} 많이 발생한 지역은 TAC {tac} PCI {pci}이고"
                    f" {cnt}번 발생하였습니다.{inca_str}"
                )
            lines.append("")

        # ─ MUTE_EXTRA (SAMS/SMBU/MCST 전체) ─────────────────────────────────
        mute_extra = feature_tables.get("MUTE_EXTRA")
        if mute_extra and mute_extra.rows:
            import re as _re
            row = mute_extra.rows[0]
            parts = []
            total_mic_count = 0
            for c in mute_extra.columns:
                raw = _col(mute_extra, row, c)
                total_mic_count += sum(int(n) for n in _re.findall(r':(\d+)회', raw))
                v = _decode_cell(c, raw)
                if v and v != "-":
                    parts.append(f"{c}는 {v}")
            if parts:
                lines.append(", ".join(parts) + "입니다.")
                if total_mic_count >= 10:
                    lines.append(f"⚠️ SAMS/SMBU/MCST 총 {total_mic_count}회 → 단말기 마이크 점검 필요")
                lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _hex_to_dec(val: str) -> str:
        """16진수 문자열을 10진수 문자열로 변환합니다. 변환 불가 시 원본 반환."""
        v = val.strip()
        if not v:
            return v
        try:
            return str(int(v, 16))
        except ValueError:
            return v

    @staticmethod
    def _read_csv(csv_path: str) -> list[dict]:
        """CSV 파일을 읽어 dict 리스트로 반환합니다."""
        try:
            rows = []
            with open(csv_path, encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    rows.append(dict(row))
            logger.info(f"CSV 읽기 완료: {csv_path} ({len(rows)}행)")
            return rows
        except Exception as e:
            logger.error(f"CSV 읽기 실패 [{csv_path}]: {e}")
            return []

    @staticmethod
    def _parse_custom_value(raw: str) -> dict:
        """custom_value JSON 문자열을 dict로 파싱합니다."""
        raw = raw.strip()
        if not raw or raw in ("nan", "None", "null"):
            return {}
        # 표준 JSON 시도
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # 작은따옴표 → 큰따옴표 변환
        try:
            return json.loads(raw.replace("'", '"'))
        except json.JSONDecodeError:
            pass
        # 정규식 fallback
        pairs = re.findall(r'"([^"]+)"\s*:\s*"([^"]*)"', raw)
        return dict(pairs)


# 싱글턴 인스턴스
data_processor = DataProcessor()
