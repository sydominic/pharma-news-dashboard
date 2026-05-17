from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

KST = ZoneInfo("Asia/Seoul")


def now_kst() -> datetime:
    """현재 시각을 한국시간(KST) timezone-aware datetime으로 반환합니다."""
    return datetime.now(KST)


def today_kst() -> date:
    """오늘 날짜를 한국시간(KST) 기준으로 반환합니다."""
    return now_kst().date()


def start_of_kst_day(value: date | datetime | str | None = None) -> datetime:
    """입력 날짜의 00:00:00을 KST timezone-aware datetime으로 반환합니다."""
    d = today_kst() if value is None else to_kst_date(value)
    return datetime.combine(d, time.min, tzinfo=KST)


def kst_cutoff_for_recent_days(days: int) -> datetime:
    """최근 N일을 KST 달력일 기준으로 계산한 시작시각을 반환합니다.

    예: KST 오늘이 18일이고 days=7이면 12일 00:00:00 KST부터입니다.
    """
    days = max(int(days or 1), 1)
    return start_of_kst_day(today_kst() - timedelta(days=days - 1))


def to_kst_timestamp(value) -> pd.Timestamp:
    """문자열/Datetime 값을 KST timezone-aware pandas Timestamp로 변환합니다.

    - timezone 정보가 있는 값은 KST로 변환합니다.
    - timezone 정보가 없는 값은 기존 CSV/수집 데이터 규칙에 맞춰 KST 시각으로 간주합니다.
    """
    if value is None:
        return pd.NaT
    try:
        if isinstance(value, str) and value.strip().lower() in {"", "nan", "none", "nat", "null"}:
            return pd.NaT
    except Exception:
        pass
    try:
        ts = pd.to_datetime(value, errors="coerce")
    except Exception:
        return pd.NaT
    if pd.isna(ts):
        return pd.NaT
    try:
        if getattr(ts, "tzinfo", None) is None:
            return pd.Timestamp(ts).tz_localize(KST)
        return pd.Timestamp(ts).tz_convert(KST)
    except Exception:
        try:
            ts2 = pd.to_datetime(str(value), errors="coerce", utc=True)
            if pd.isna(ts2):
                return pd.NaT
            return pd.Timestamp(ts2).tz_convert(KST)
        except Exception:
            return pd.NaT


def to_kst_series(values) -> pd.Series:
    """Series/list를 KST Timestamp Series로 변환합니다."""
    if isinstance(values, pd.Series):
        src = values
    else:
        src = pd.Series(values)
    converted = src.apply(to_kst_timestamp)
    try:
        return pd.to_datetime(converted, errors="coerce")
    except Exception:
        return converted


def to_kst_date(value) -> date:
    ts = to_kst_timestamp(value)
    if pd.isna(ts):
        return today_kst()
    return ts.date()


def format_kst_datetime(value) -> str:
    ts = to_kst_timestamp(value)
    if pd.isna(ts):
        return ""
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def format_kst_date(value) -> str:
    ts = to_kst_timestamp(value)
    if pd.isna(ts):
        return ""
    return ts.strftime("%Y-%m-%d")


def format_kst_time(value) -> str:
    ts = to_kst_timestamp(value)
    if pd.isna(ts):
        return ""
    return ts.strftime("%H:%M")


def to_supabase_timestamptz(value) -> str | None:
    """Supabase timestamptz 저장용 ISO 문자열(+09:00 포함)을 반환합니다."""
    ts = to_kst_timestamp(value)
    if pd.isna(ts):
        return None
    return ts.isoformat()
