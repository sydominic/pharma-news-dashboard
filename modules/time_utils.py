from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

KST = ZoneInfo("Asia/Seoul")
FUTURE_NEWS_TOLERANCE_MINUTES = 30


def now_kst() -> datetime:
    """현재 시각을 한국시간(KST) timezone-aware datetime으로 반환합니다."""
    return datetime.now(KST)


def today_kst() -> date:
    """오늘 날짜를 한국시간(KST) 기준으로 반환합니다."""
    return now_kst().date()


def _is_blank(value) -> bool:
    try:
        return value is None or str(value).strip().lower() in {"", "nan", "none", "nat", "null"}
    except Exception:
        return value is None


def _parse_to_kst_no_guard(value) -> pd.Timestamp:
    """입력값을 일단 KST Timestamp로 변환하되, 미래시간 보정은 하지 않습니다."""
    if _is_blank(value):
        return pd.NaT
    try:
        ts = pd.to_datetime(value, errors="coerce")
    except Exception:
        return pd.NaT
    if pd.isna(ts):
        return pd.NaT
    try:
        ts = pd.Timestamp(ts)
        if getattr(ts, "tzinfo", None) is None:
            return ts.tz_localize(KST)
        return ts.tz_convert(KST)
    except Exception:
        try:
            ts2 = pd.to_datetime(str(value), errors="coerce", utc=True)
            if pd.isna(ts2):
                return pd.NaT
            return pd.Timestamp(ts2).tz_convert(KST)
        except Exception:
            return pd.NaT


def _normalize_future_news_time(
    ts: pd.Timestamp,
    reference: pd.Timestamp | None = None,
    max_future_minutes: int = FUTURE_NEWS_TOLERANCE_MINUTES,
) -> pd.Timestamp:
    """뉴스 발행시각 미래 과보정을 보정합니다.

    Google News RSS/기존 Supabase 캐시에 같은 시각이 UTC처럼 저장되면 화면에 +9시간 된
    미래 시간이 표시될 수 있습니다. 단순히 현재시각(now)만 보지 않고, 기사 수집시각
    `collected_at`이 있으면 그 값을 우선 기준으로 삼습니다.

    예: collected_at=2026-05-18 08:57 KST, published_at=2026-05-18 17:24 KST
    → 수집시각보다 8시간 이상 미래이므로 9시간 차감해 08:24 KST로 보정합니다.
    """
    if pd.isna(ts):
        return ts
    try:
        ts = pd.Timestamp(ts)
        if getattr(ts, "tzinfo", None) is None:
            ts = ts.tz_localize(KST)
        else:
            ts = ts.tz_convert(KST)

        ref = reference
        if ref is None or pd.isna(ref):
            ref = pd.Timestamp(now_kst())
        else:
            ref = pd.Timestamp(ref)
            if getattr(ref, "tzinfo", None) is None:
                ref = ref.tz_localize(KST)
            else:
                ref = ref.tz_convert(KST)

        tolerance = pd.Timedelta(minutes=max_future_minutes)
        if ts > ref + tolerance:
            shifted = ts - pd.Timedelta(hours=9)
            if shifted <= ref + tolerance:
                return shifted
        return ts
    except Exception:
        return ts


def to_kst_timestamp(value, reference=None) -> pd.Timestamp:
    """문자열/Datetime 값을 KST timezone-aware pandas Timestamp로 변환합니다.

    - timezone 정보가 없는 값은 기존 수집/CSV 규칙상 KST 시각으로 간주합니다.
    - timezone 정보가 있는 값은 KST로 변환합니다.
    - 단, 결과가 수집시각 또는 현재시각보다 과도하게 미래이면 Google News UTC 오인식으로 보고 9시간 보정합니다.
    """
    ts = _parse_to_kst_no_guard(value)
    if pd.isna(ts):
        return pd.NaT
    ref_ts = _parse_to_kst_no_guard(reference) if not _is_blank(reference) else None
    return _normalize_future_news_time(ts, reference=ref_ts)


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


def to_kst_series_with_reference(values, references=None) -> pd.Series:
    """값 Series와 기준시각 Series(collected_at 등)를 같이 사용해 KST Timestamp로 변환합니다."""
    src = values if isinstance(values, pd.Series) else pd.Series(values)
    if references is None:
        refs = pd.Series([None] * len(src), index=src.index)
    else:
        refs = references if isinstance(references, pd.Series) else pd.Series(references, index=src.index)
        refs = refs.reindex(src.index)
    converted = pd.Series([to_kst_timestamp(v, r) for v, r in zip(src.tolist(), refs.tolist())], index=src.index)
    try:
        return pd.to_datetime(converted, errors="coerce")
    except Exception:
        return converted


def start_of_kst_day(value: date | datetime | str | None = None) -> datetime:
    """입력 날짜의 00:00:00을 KST timezone-aware datetime으로 반환합니다."""
    d = today_kst() if value is None else to_kst_date(value)
    return datetime.combine(d, time.min, tzinfo=KST)


def kst_cutoff_for_recent_days(days: int) -> datetime:
    """최근 N일을 KST 달력일 기준으로 계산한 시작시각을 반환합니다."""
    days = max(int(days or 1), 1)
    return start_of_kst_day(today_kst() - timedelta(days=days - 1))


def to_kst_date(value) -> date:
    ts = to_kst_timestamp(value)
    if pd.isna(ts):
        return today_kst()
    return ts.date()


def format_kst_datetime(value, reference=None) -> str:
    ts = to_kst_timestamp(value, reference=reference)
    if pd.isna(ts):
        return ""
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def format_kst_date(value, reference=None) -> str:
    ts = to_kst_timestamp(value, reference=reference)
    if pd.isna(ts):
        return ""
    return ts.strftime("%Y-%m-%d")


def format_kst_time(value, reference=None) -> str:
    ts = to_kst_timestamp(value, reference=reference)
    if pd.isna(ts):
        return ""
    return ts.strftime("%H:%M")


def to_supabase_timestamptz(value, reference=None) -> str | None:
    """Supabase timestamptz 저장용 ISO 문자열(+09:00 포함)을 반환합니다."""
    ts = to_kst_timestamp(value, reference=reference)
    if pd.isna(ts):
        return None
    return ts.isoformat()
