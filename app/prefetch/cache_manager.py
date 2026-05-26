"""
캐시 관리 — SN별 사전 쿼리 결과(CSV/xlsx) 파일 존재 여부 확인 및 목록 조회
"""
import logging
from datetime import datetime
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

_EXTS = [".csv", ".xlsx", ".xls"]


def _find_cache_file(sn: str) -> Path | None:
    """SN에 해당하는 캐시 파일을 csv → xlsx → xls 순서로 찾아 반환합니다."""
    base = Path(settings.CSV_DOWNLOAD_PATH)
    for ext in _EXTS:
        p = base / f"{sn}_inputdata{ext}"
        if p.exists():
            return p
    return None


def get_cache_csv_path(sn: str) -> Path:
    return Path(settings.CSV_DOWNLOAD_PATH) / f"{sn}_inputdata.csv"


def is_cached(sn: str, max_age_hours: int | None = None) -> bool:
    """SN의 캐시 파일(csv/xlsx/xls)이 존재하고 유효 시간 이내인지 확인합니다."""
    if max_age_hours is None:
        max_age_hours = settings.CACHE_MAX_AGE_HOURS
    path = _find_cache_file(sn)
    if path is None:
        return False
    age_h = (datetime.now().timestamp() - path.stat().st_mtime) / 3600
    return age_h < max_age_hours


def get_cached_csv_path(sn: str) -> str | None:
    """캐시 파일 경로 반환 (csv/xlsx/xls 모두 탐색). 없으면 None."""
    path = _find_cache_file(sn)
    return str(path) if path is not None else None


def list_cached_sns() -> list[dict]:
    """캐시된 SN 목록을 최신순으로 반환합니다."""
    cache_dir = Path(settings.CSV_DOWNLOAD_PATH)
    if not cache_dir.exists():
        return []
    seen: dict[str, Path] = {}
    for ext in _EXTS:
        for f in cache_dir.glob(f"*_inputdata{ext}"):
            sn = f.stem.replace("_inputdata", "")
            if sn not in seen:
                seen[sn] = f
    result = []
    for sn, f in sorted(seen.items(), key=lambda x: x[1].stat().st_mtime, reverse=True):
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        age_h = (datetime.now().timestamp() - f.stat().st_mtime) / 3600
        result.append({
            "sn": sn,
            "cached_at": mtime.strftime("%Y-%m-%d %H:%M"),
            "age_hours": round(age_h, 1),
            "fresh": age_h < settings.CACHE_MAX_AGE_HOURS,
            "file": f.name,
        })
    return result
