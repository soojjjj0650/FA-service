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
        ("Band",  "Band"),
        ("UBMT",  "UBMT"),
        ("RSMT",  "RSMT"),
        ("RNMT",  "RNMT"),
        ("DBMT",  "DBMT"),
        ("ECNT",  "ECNT"),
        ("RSRP",  "RSRP"),
        ("RSCP",  "RSCP"),
        ("SINR",  "SINR"),
        ("BLER",  "BLER"),
    ]),
    # 추후 추가: DROP, ATTS, CEND, SCGF, ATTF, ATTI, SIMD, RLFI, NSVC, CRSH 등
}


# ─── 16진수 → 10진수 변환이 필요한 컬럼 (표시명 기준, 전 feature 공통) ────────
HEX_COLUMNS: set[str] = {"TAC", "LAC"}


# ─── feature별 집계 규칙 ──────────────────────────────────────────────────────
# group_by : 동일 조합으로 묶을 표시명 컬럼 목록
# sum      : 합계를 낼 컬럼
# avg      : 평균을 낼 컬럼 (소수점 1자리)
# first    : 그룹 내 첫 번째 값을 그대로 사용할 컬럼
# drop     : 집계 후 제거할 컬럼
# sort_by  : 집계 후 내림차순 정렬 기준 컬럼
FEATURE_AGGREGATION: dict[str, dict] = {
    "MUTE": {
        "group_by": ["PLMN", "ACT", "TAC", "LAC", "PCI", "DLCh"],
        "sum":      ["UBMT", "RSMT", "RNMT", "DBMT", "ECNT"],
        "avg":      ["RSRP", "RSCP", "SINR", "BLER"],
        "first":    ["Band"],
        "drop":     ["Date", "Time"],
        "sort_by":  "ECNT",
    },
}


# ─── 데이터 클래스 ────────────────────────────────────────────────────────────

@dataclass
class FeatureTable:
    feature: str
    columns: list[str]
    rows: list[list[str]]

    def to_text(self) -> str:
        """AI Agent 전송용 plain-text 테이블"""
        if not self.rows:
            return f"[{self.feature}] 데이터 없음"
        header = " | ".join(self.columns)
        sep = "-" * max(len(header), 20)
        data_lines = [" | ".join(str(v) for v in row) for row in self.rows]
        return "\n".join([f"[{self.feature}] {len(self.rows)}건", header, sep] + data_lines)

    def to_html(self) -> str:
        """챗봇 표시용 HTML 테이블"""
        if not self.rows:
            return (
                f'<div class="feat-table-wrap">'
                f'<div class="feat-label">{self.feature}</div>'
                f'<p class="no-data">데이터 없음</p></div>'
            )
        th = "".join(f"<th>{c}</th>" for c in self.columns)
        tbody = "".join(
            "<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>"
            for row in self.rows
        )
        return (
            f'<div class="feat-table-wrap">'
            f'<div class="feat-label">{self.feature}'
            f' <span class="feat-count">({len(self.rows)}건)</span></div>'
            f'<div class="tbl-scroll"><table>'
            f'<thead><tr>{th}</tr></thead>'
            f'<tbody>{tbody}</tbody>'
            f'</table></div></div>'
        )


@dataclass
class ProcessedData:
    sn: str
    summary_text: str       # AI Agent 전송 텍스트
    ai_prompt: str          # AI Agent 최종 프롬프트
    feature_tables: dict[str, FeatureTable] = field(default_factory=dict)
    html_tables: str = ""   # 챗봇 HTML 렌더링용
    error: str | None = None

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
                ai_prompt="",
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
                ai_prompt="",
                error="데이터 없음",
            )

        feature_tables = self._build_feature_tables(rows)
        summary = self._build_summary(query_result.sn, rows, feature_tables)
        prompt = self._build_ai_prompt(query_result.sn, summary)
        html_tables = "".join(t.to_html() for t in feature_tables.values())

        logger.info(
            f"데이터 가공 완료 - SN: {query_result.sn}, "
            f"features: {list(feature_tables.keys())}, 총 {len(rows)}건"
        )

        return ProcessedData(
            sn=query_result.sn,
            summary_text=summary,
            ai_prompt=prompt,
            feature_tables=feature_tables,
            html_tables=html_tables,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────────────────

    def _build_feature_tables(self, rows: list[dict]) -> dict[str, FeatureTable]:
        """feature별로 그룹화하고 FeatureTable 목록을 반환합니다."""
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            feat = str(row.get("feature", "")).strip().upper()
            if feat:
                grouped.setdefault(feat, []).append(row)

        tables: dict[str, FeatureTable] = {}
        for feat, feat_rows in grouped.items():
            col_map = FEATURE_COLUMNS.get(feat)
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
                        else:
                            val = cv.get(json_key, "")
                            if col_name in HEX_COLUMNS:
                                val = self._hex_to_dec(val)
                        tr.append(val)
                    table_rows.append(tr)

                columns = list(col_map.keys())
                agg_rows = self._aggregate_rows(feat, columns, table_rows)

                # drop 컬럼 제거
                drop_cols = set(FEATURE_AGGREGATION.get(feat, {}).get("drop", []))
                if drop_cols:
                    keep_idx = [i for i, c in enumerate(columns) if c not in drop_cols]
                    columns  = [columns[i] for i in keep_idx]
                    agg_rows = [[row[i] for i in keep_idx] for row in agg_rows]

                # 내림차순 정렬
                sort_col = FEATURE_AGGREGATION.get(feat, {}).get("sort_by")
                if sort_col and sort_col in columns:
                    si = columns.index(sort_col)
                    agg_rows.sort(key=lambda r: _safe_float(r[si]), reverse=True)

                tables[feat] = FeatureTable(
                    feature=feat,
                    columns=columns,
                    rows=agg_rows,
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

        return tables

    def _aggregate_rows(
        self,
        feat: str,
        columns: list[str],
        rows: list[list[str]],
    ) -> list[list[str]]:
        """FEATURE_AGGREGATION 규칙에 따라 행을 그룹화·집계합니다.
        집계 규칙이 없는 feature는 원본 rows를 그대로 반환합니다."""
        agg_cfg = FEATURE_AGGREGATION.get(feat)
        if not agg_cfg or not rows:
            return rows

        col_idx = {c: i for i, c in enumerate(columns)}
        group_by_cols = [c for c in agg_cfg["group_by"] if c in col_idx]
        sum_cols  = [c for c in agg_cfg.get("sum",  []) if c in col_idx]
        avg_cols  = [c for c in agg_cfg.get("avg",  []) if c in col_idx]

        if not group_by_cols:
            return rows

        # 그룹 키 → 해당 rows 묶기
        groups: dict[tuple, list[list[str]]] = {}
        for row in rows:
            key = tuple(row[col_idx[c]] for c in group_by_cols)
            groups.setdefault(key, []).append(row)

        result = []
        for group_rows in groups.values():
            merged = list(group_rows[0])  # 기준행 (Date·Time·first 값 유지)

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

            # 평균 컬럼 (소수점 1자리)
            for col in avg_cols:
                vals = []
                for r in group_rows:
                    try:
                        v = r[col_idx[col]]
                        if v:
                            vals.append(float(v))
                    except (ValueError, TypeError):
                        pass
                merged[col_idx[col]] = f"{sum(vals)/len(vals):.1f}" if vals else ""

            result.append(merged)

        logger.debug(
            f"[{feat}] 집계 완료: 원본 {len(rows)}건 → 집계 {len(result)}건 "
            f"(group_by={group_by_cols})"
        )
        return result

    def _build_summary(
        self,
        sn: str,
        rows: list[dict],
        feature_tables: dict[str, FeatureTable],
    ) -> str:
        """AI Agent 전송용 텍스트 요약을 생성합니다."""
        dates = [str(r.get("Date", "")) for r in rows if r.get("Date")]
        date_range = f"{min(dates)} ~ {max(dates)}" if dates else "날짜 없음"

        lines = [
            f"=== SN: {sn} 네트워크 이벤트 데이터 ===",
            f"기간: {date_range}, 총 {len(rows)}건",
            "",
        ]
        for table in feature_tables.values():
            lines.append(table.to_text())
            lines.append("")

        return "\n".join(lines)

    def _build_ai_prompt(self, sn: str, summary: str) -> str:
        return (
            f"다음은 단말기(SN: {sn})에서 수집된 네트워크 이벤트 데이터입니다.\n\n"
            f"{summary}\n\n"
            f"위 데이터를 분석하여 한국어로 간결하게 답변해 주세요:\n"
            f"1. 주요 이벤트 발생 현황 요약\n"
            f"2. MUTE/DROP 발생 지역 (PLMN, TAC, PCI 기준)\n"
            f"3. NW 품질 이슈 여부 (RSRP, SINR, BLER 기준)\n"
            f"4. FA 권고 조치사항\n"
        )

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
