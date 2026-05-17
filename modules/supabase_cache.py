from __future__ import annotations

from datetime import timedelta
from typing import Any

import pandas as pd

from .news_cleaner import STANDARD_COLUMNS, make_empty_frame, repair_and_reclassify
from .time_utils import kst_cutoff_for_recent_days, now_kst, to_kst_series, to_supabase_timestamptz

TABLE_ARTICLES = "news_articles"
TABLE_LOG = "collection_log"
CACHE_DAYS = 30

LEGACY_COLUMNS = [
    "uid", "published_at", "date", "time", "source", "category", "keywords", "importance", "qa_flag",
    "title", "summary", "link", "rss_query_name", "rss_query", "collected_at"
]



def _safe_secret(secrets: Any, *names: str) -> str:
    for name in names:
        try:
            value = secrets.get(name, "")
        except Exception:
            value = ""
        if value:
            return str(value).strip()
    return ""


def get_supabase_settings(secrets: Any) -> tuple[str, str]:
    url = _safe_secret(secrets, "SUPABASE_URL")
    key = _safe_secret(secrets, "SUPABASE_KEY", "SUPABASE_ANON_KEY")
    return url, key


def is_supabase_configured(secrets: Any) -> bool:
    url, key = get_supabase_settings(secrets)
    return bool(url and key)


def get_client(secrets: Any):
    url, key = get_supabase_settings(secrets)
    if not url or not key:
        return None
    from supabase import create_client
    return create_client(url, key)


def _cutoff_iso(days: int = CACHE_DAYS) -> str:
    # KST 달력일 기준 최근 N일의 시작시각입니다. Supabase timestamptz에는 +09:00 오프셋 포함 ISO로 전달합니다.
    return kst_cutoff_for_recent_days(days).isoformat()


def load_recent_articles(secrets: Any, days: int = CACHE_DAYS) -> pd.DataFrame:
    client = get_client(secrets)
    if client is None:
        return make_empty_frame()
    cutoff = _cutoff_iso(days)
    response = (
        client.table(TABLE_ARTICLES)
        .select("*")
        .gte("published_at", cutoff)
        .order("published_at", desc=True)
        .limit(10000)
        .execute()
    )
    data = getattr(response, "data", None) or []
    if not data:
        return make_empty_frame()
    df = pd.DataFrame(data)
    for col in STANDARD_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return repair_and_reclassify(df[STANDARD_COLUMNS], force=False)


def upsert_articles(secrets: Any, df: pd.DataFrame, days: int = CACHE_DAYS) -> int:
    client = get_client(secrets)
    if client is None or df is None or df.empty:
        return 0
    work = repair_and_reclassify(df, force=False).copy()
    work["published_at_dt"] = to_kst_series(work["published_at"])
    cutoff = pd.Timestamp(kst_cutoff_for_recent_days(days))
    work = work[work["published_at_dt"] >= cutoff].drop(columns=["published_at_dt"], errors="ignore")
    if work.empty:
        return 0
    records = []
    now_iso = now_kst().isoformat()
    for _, row in work.iterrows():
        rec = {col: row.get(col, "") for col in STANDARD_COLUMNS}
        rec["qa_flag"] = bool(rec.get("qa_flag", False))
        # Supabase column is timestamptz; empty string cannot be cast.
        rec["published_at"] = to_supabase_timestamptz(rec.get("published_at", ""))
        rec["cache_updated_at"] = now_iso
        records.append(rec)
    # Chunk to avoid payload limits.
    # If the Supabase table has not yet been migrated to v1.34 columns, retry with legacy columns
    # so the dashboard still runs; run supabase_migration_v28.sql to persist article summaries in Supabase.
    total = 0
    for i in range(0, len(records), 500):
        chunk = records[i:i + 500]
        try:
            client.table(TABLE_ARTICLES).upsert(chunk, on_conflict="uid").execute()
        except Exception as exc:
            msg = str(exc).lower()
            if any(name in msg for name in ["article_summary", "article_text", "sub_tags", "classification_reason", "classification_score", "body_fetch_status", "column"]):
                legacy_chunk = [{k: rec.get(k, "") for k in LEGACY_COLUMNS} | {"cache_updated_at": rec.get("cache_updated_at")} for rec in chunk]
                client.table(TABLE_ARTICLES).upsert(legacy_chunk, on_conflict="uid").execute()
            else:
                raise
        total += len(chunk)
    return total


def prune_old_articles(secrets: Any, days: int = CACHE_DAYS) -> None:
    client = get_client(secrets)
    if client is None:
        return
    cutoff = _cutoff_iso(days)
    client.table(TABLE_ARTICLES).delete().lt("published_at", cutoff).execute()


def write_collection_log(secrets: Any, status: str, added_count: int = 0, total_count: int = 0, error_message: str = "") -> None:
    client = get_client(secrets)
    if client is None:
        return
    rec = {
        "id": "latest",
        "status": status,
        "added_count": int(added_count or 0),
        "total_count": int(total_count or 0),
        "error_message": str(error_message or "")[:1000],
        "collected_at": now_kst().isoformat(),
    }
    client.table(TABLE_LOG).upsert(rec, on_conflict="id").execute()


def read_latest_log(secrets: Any) -> dict:
    client = get_client(secrets)
    if client is None:
        return {}
    response = client.table(TABLE_LOG).select("*").eq("id", "latest").limit(1).execute()
    data = getattr(response, "data", None) or []
    return data[0] if data else {}
