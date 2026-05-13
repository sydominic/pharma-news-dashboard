from __future__ import annotations

import calendar
import hashlib
import html
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import feedparser
import pandas as pd
import requests
from bs4 import BeautifulSoup

from .article_enricher import enrich_article

KST = ZoneInfo("Asia/Seoul")
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


def load_rss_config(config_path: str | Path) -> Dict[str, Any]:
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _to_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        dt = pd.to_datetime(value, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.date()
    except Exception:
        return None


def add_date_operators(query: str, start_date=None, end_date=None) -> str:
    """Google News RSS 검색식에 after/before 날짜 조건을 붙인다.

    before:는 Google 검색에서 보통 해당 날짜 이전으로 해석되므로 종료일을 포함하기 위해 +1일을 사용한다.
    """
    q = (query or "").strip()
    start = _to_date(start_date)
    end = _to_date(end_date)
    # 기존 after/before가 들어간 검색식은 중복 삽입하지 않음
    if start and "after:" not in q:
        q += f" after:{start.isoformat()}"
    if end and "before:" not in q:
        q += f" before:{(end + timedelta(days=1)).isoformat()}"
    return q.strip()


def build_google_news_rss_url(query: str, hl: str = "ko", gl: str = "KR", ceid: str = "KR:ko") -> str:
    return f"{GOOGLE_NEWS_RSS}?q={quote_plus(query)}&hl={quote_plus(hl)}&gl={quote_plus(gl)}&ceid={quote_plus(ceid)}"


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).strip()
    for _ in range(3):
        new_text = html.unescape(text)
        if new_text == text:
            break
        text = new_text
    soup = BeautifulSoup(text, "html.parser")
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"https?://\S+", " ", text)
    text = text.replace("nan", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if text.lower() in {"nan", "none", "null", "nat"}:
        return ""
    return text[:400]


def parse_datetime(entry: Dict[str, Any]) -> str:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        dt_utc = datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
        return dt_utc.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")

    published = entry.get("published") or entry.get("updated")
    if published:
        try:
            parsed_dt = pd.to_datetime(published, utc=True, errors="coerce")
            if not pd.isna(parsed_dt):
                return parsed_dt.tz_convert("Asia/Seoul").strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")


def source_from_entry(entry: Dict[str, Any], source_hint: str = "") -> str:
    source = entry.get("source")
    if isinstance(source, dict):
        title = source.get("title")
        if title:
            return str(title).strip()
    if entry.get("author"):
        return str(entry.get("author")).strip()
    return source_hint or "Google News"


def make_uid(title: str, source: str, published_at: str) -> str:
    raw = f"{title}|{source}|{published_at[:10]}".lower().strip()
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:18]


def fetch_feed(url: str, timeout_sec: int = 12) -> feedparser.FeedParserDict:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    response = requests.get(url, headers=headers, timeout=timeout_sec)
    response.raise_for_status()
    return feedparser.parse(response.content)


def collect_google_news(config_path: str | Path, start_date=None, end_date=None, max_items_per_query: int | None = None) -> pd.DataFrame:
    config = load_rss_config(config_path)
    settings = config.get("settings", {})
    hl = settings.get("hl", "ko")
    gl = settings.get("gl", "KR")
    ceid = settings.get("ceid", "KR:ko")
    max_items = int(max_items_per_query or settings.get("max_items_per_query", 80))
    timeout_sec = int(settings.get("timeout_sec", 12))
    fetch_article_body = bool(settings.get("fetch_article_body", True))
    article_body_timeout_sec = int(settings.get("article_body_timeout_sec", 5))
    article_body_max_chars = int(settings.get("article_body_max_chars", 6000))
    max_body_fetch_per_run = int(settings.get("max_body_fetch_per_run", 80))
    collected_at = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

    rows: List[Dict[str, Any]] = []
    errors: List[str] = []

    for q in config.get("queries", []):
        if not q.get("enabled", True):
            continue
        query_name = q.get("name", "RSS Query")
        base_query = q.get("query", "")
        query = add_date_operators(base_query, start_date=start_date, end_date=end_date)
        source_hint = q.get("source_hint", "")
        if not query.strip():
            continue

        url = build_google_news_rss_url(query, hl=hl, gl=gl, ceid=ceid)
        try:
            feed = fetch_feed(url, timeout_sec=timeout_sec)
        except Exception as exc:
            errors.append(f"{query_name}: {exc}")
            continue

        for entry in feed.entries[:max_items]:
            title = str(entry.get("title", "")).strip()
            if not title:
                continue
            source = source_from_entry(entry, source_hint=source_hint)
            published_at = parse_datetime(entry)
            summary = strip_html(entry.get("summary", ""))
            link = str(entry.get("link", "")).strip()
            uid = make_uid(title, source, published_at)
            rows.append(
                {
                    "uid": uid,
                    "title": title,
                    "source": source,
                    "published_at": published_at,
                    "summary": summary,
                    "article_summary": "",
                    "article_text": "",
                    "body_fetch_status": "대기",
                    "link": link,
                    "rss_query_name": query_name,
                    "rss_query": query,
                    "rss_url": url,
                    "collected_at": collected_at,
                }
            )
        time.sleep(0.12)

    df = pd.DataFrame(rows)
    if df.empty:
        out = pd.DataFrame(columns=[
            "uid", "title", "source", "published_at", "summary", "article_summary", "article_text", "body_fetch_status", "link", "rss_query_name", "rss_query", "rss_url", "collected_at"
        ])
        out.attrs["errors"] = errors
        return out

    df = df.drop_duplicates(subset=["uid"], keep="first")
    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")
    df = df.sort_values("published_at", ascending=False).reset_index(drop=True)

    # 내용 기반 분류와 화면 요약을 위해 원문 본문 일부를 가능한 범위에서 수집합니다.
    # 너무 느려지지 않도록 실행당 수집 상한을 둡니다. 본문 실패 시 RSS 요약 기반으로 대체됩니다.
    enrich_limit = max(0, min(max_body_fetch_per_run, len(df)))
    for idx in range(len(df)):
        row = df.iloc[idx]
        should_fetch = fetch_article_body and idx < enrich_limit
        enriched = enrich_article(
            title=str(row.get("title", "")),
            rss_summary=str(row.get("summary", "")),
            link=str(row.get("link", "")),
            fetch_body=should_fetch,
            timeout_sec=article_body_timeout_sec,
            max_chars=article_body_max_chars,
        )
        df.at[idx, "article_text"] = enriched.get("article_text", "")
        df.at[idx, "article_summary"] = enriched.get("article_summary", "")
        df.at[idx, "body_fetch_status"] = enriched.get("body_fetch_status", "RSS요약사용")
        if should_fetch:
            time.sleep(0.05)

    df["published_at"] = df["published_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df.attrs["errors"] = errors
    return df.reset_index(drop=True)
