"""
캐시 관리 — SN별 사전 쿼리 결과(CSV) 파일 존재 여부 확인 및 목록 조회
"""
import logging
from datetime import datetime
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


def get_cache_csv_path(sn: str) -> Path:
    return Path(settings.CSV_DOWNLOAD_PATH) / f"{sn}_inputdata.csv"


def is_cached(sn: str, max_age_hours: int | None = None) -> bool:
    """SN의 캐시 CSV가 존재하고 유효 시간 이내인지 확인합니다."""
    if max_age_hours is None:
        max_age_hours = settings.CACHE_MAX_AGE_HOURS
    path = get_cache_csv_path(sn)
    if not path.exists():
        return False
    age_h = (datetime.now().timestamp() - path.stat().st_mtime) / 3600
    return age_h < max_age_hours


def get_cached_csv_path(sn: str) -> str | None:
    """캐시 CSV 경로 반환. 없으면 None."""
    path = get_cache_csv_path(sn)
    return str(path) if path.exists() else None


def list_cached_sns() -> list[dict]:
    """캐시된 SN 목록을 최신순으로 반환합니다."""
    cache_dir = Path(settings.CSV_DOWNLOAD_PATH)
    if not cache_dir.exists():
        return []
    result = []
    for csv_file in sorted(
        cache_dir.glob("*_inputdata.csv"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    ):
        sn = csv_file.stem.replace("_inputdata", "")
        mtime = datetime.fromtimestamp(csv_file.stat().st_mtime)
        age_h = (datetime.now().timestamp() - csv_file.stat().st_mtime) / 3600
        result.append({
            "sn": sn,
            "cached_at": mtime.strftime("%Y-%m-%d %H:%M"),
            "age_hours": round(age_h, 1),
            "fresh": age_h < settings.CACHE_MAX_AGE_HOURS,
        })
    return result
