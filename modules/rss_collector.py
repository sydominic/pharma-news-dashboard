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
import feedparser
import pandas as pd
import requests
from bs4 import BeautifulSoup

from .article_enricher import enrich_article
from .news_cleaner import is_excluded_notice_article
from .time_utils import KST, now_kst, to_kst_date, to_kst_series_with_reference
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
        return to_kst_date(value)
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


def build_google_news_rss_url(
    query: str,
    hl: str = "ko",
    gl: str = "KR",
    ceid: str = "KR:ko",
    cache_bust: bool = True,
) -> str:
    """Google News RSS URL을 생성합니다.

    Google News RSS/CDN이 같은 URL에 대해 오래된 응답을 반환하는 경우가 있어,
    수동 수집 시점마다 `_cb` 파라미터를 붙여 stale feed 가능성을 낮춥니다.
    Google News가 이 파라미터를 검색조건으로 보지는 않지만, HTTP 캐시 키는 달라집니다.
    """
    url = f"{GOOGLE_NEWS_RSS}?q={quote_plus(query)}&hl={quote_plus(hl)}&gl={quote_plus(gl)}&ceid={quote_plus(ceid)}"
    if cache_bust:
        url += f"&_cb={int(time.time())}"
    return url


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


def _as_ref_timestamp(value: str | None):
    if not value:
        return pd.Timestamp(now_kst())
    try:
        ts = pd.to_datetime(value, errors="coerce")
        if pd.isna(ts):
            return pd.Timestamp(now_kst())
        ts = pd.Timestamp(ts)
        if getattr(ts, "tzinfo", None) is None:
            return ts.tz_localize(KST)
        return ts.tz_convert(KST)
    except Exception:
        return pd.Timestamp(now_kst())


def _choose_plausible_news_time(candidates: list[pd.Timestamp], reference: str | None = None) -> pd.Timestamp | None:
    """Google News RSS 발행시각 후보 중 가장 그럴듯한 KST 시각을 선택합니다.

    같은 RSS 항목이 언론사/Google 인덱싱 상태에 따라 다음 두 형태로 관찰될 수 있습니다.
    - GMT/UTC 시각이 정상적으로 들어온 경우: UTC → KST 변환이 맞음
    - 이미 KST clock-time인데 GMT처럼 표시되는 경우: clock-time을 KST로 읽는 것이 맞음

    그래서 두 후보를 모두 만든 뒤, 수집시각보다 미래가 아닌 후보 중 가장 최신값을 선택합니다.
    이 방식이면 오전에는 17:24 같은 미래시간 표시를 막고, 오후에는 04:30으로 9시간 당겨지는 문제도 막습니다.
    """
    ref = _as_ref_timestamp(reference)
    tolerance = pd.Timedelta(minutes=30)
    norm: list[pd.Timestamp] = []
    for c in candidates:
        if c is None or pd.isna(c):
            continue
        try:
            ts = pd.Timestamp(c)
            if getattr(ts, "tzinfo", None) is None:
                ts = ts.tz_localize(KST)
            else:
                ts = ts.tz_convert(KST)
            # 너무 오래된 값은 이번 수집기간에서 의미가 낮지만, 필터링은 Google query/앱 필터가 담당한다.
            norm.append(ts)
        except Exception:
            continue
    if not norm:
        return None
    # 중복 제거
    uniq = []
    seen = set()
    for ts in norm:
        key = ts.strftime("%Y-%m-%d %H:%M:%S%z")
        if key not in seen:
            seen.add(key)
            uniq.append(ts)
    plausible = [ts for ts in uniq if ts <= ref + tolerance]
    if plausible:
        return max(plausible)
    # 전부 미래라면 가장 덜 미래인 후보를 쓰되, 뒤에서 time_utils의 미래가드가 한 번 더 방어한다.
    return min(uniq)


def parse_datetime(entry: Dict[str, Any], collected_at: str | None = None) -> str:
    """Google News RSS 발행시각을 KST 표시용 문자열로 변환합니다.

    핵심 원칙:
    1) UTC로 해석한 KST 후보와 RSS clock-time을 KST로 읽은 후보를 모두 만든다.
    2) `collected_at`보다 미래가 아닌 후보 중 가장 최신값을 쓴다.
    3) 이렇게 해야 오전에는 +9시간 미래 표시를 막고, 오후에는 -9시간 과소표시를 막을 수 있다.
    """
    candidates: list[pd.Timestamp] = []

    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            # 후보 A: RSS clock-time을 KST로 해석
            candidates.append(pd.Timestamp(datetime(parsed.tm_year, parsed.tm_mon, parsed.tm_mday, parsed.tm_hour, parsed.tm_min, parsed.tm_sec, tzinfo=KST)))
            # 후보 B: RSS clock-time을 UTC로 해석 후 KST 변환
            candidates.append(pd.Timestamp(datetime(parsed.tm_year, parsed.tm_mon, parsed.tm_mday, parsed.tm_hour, parsed.tm_min, parsed.tm_sec, tzinfo=timezone.utc)).tz_convert(KST))
        except Exception:
            pass

    published = entry.get("published") or entry.get("updated")
    if published:
        try:
            parsed_dt = pd.to_datetime(published, errors="coerce")
            if not pd.isna(parsed_dt):
                ts = pd.Timestamp(parsed_dt)
                # 후보 C: 문자열 timezone을 존중해 KST 변환
                if getattr(ts, "tzinfo", None) is None:
                    candidates.append(ts.tz_localize(KST))
                else:
                    candidates.append(ts.tz_convert(KST))
                # 후보 D: 문자열의 clock-time만 KST로 해석
                candidates.append(pd.Timestamp(datetime(ts.year, ts.month, ts.day, ts.hour, ts.minute, ts.second, tzinfo=KST)))
        except Exception:
            pass

    chosen = _choose_plausible_news_time(candidates, reference=collected_at)
    if chosen is None or pd.isna(chosen):
        chosen = pd.Timestamp(now_kst())
    return chosen.strftime("%Y-%m-%d %H:%M:%S")

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
        "Cache-Control": "no-cache, no-store, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
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
    collected_at = now_kst().strftime("%Y-%m-%d %H:%M:%S")

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
            published_at = parse_datetime(entry, collected_at=collected_at)
            summary = strip_html(entry.get("summary", ""))
            link = str(entry.get("link", "")).strip()
            if is_excluded_notice_article(title=title, summary=summary, source=source, rss_query=query, link=link):
                continue
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
    df["published_at"] = to_kst_series_with_reference(df["published_at"], df.get("collected_at"))
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
        article_text = enriched.get("article_text", "")
        if is_excluded_notice_article(title=row.get("title", ""), summary=row.get("summary", ""), article_text=article_text, source=row.get("source", ""), rss_query=row.get("rss_query", ""), link=row.get("link", "")):
            df.at[idx, "_drop_noise"] = True
            continue
        df.at[idx, "article_text"] = article_text
        df.at[idx, "article_summary"] = ""
        df.at[idx, "body_fetch_status"] = enriched.get("body_fetch_status", "RSS요약사용")
        if should_fetch:
            time.sleep(0.05)

    if "_drop_noise" in df.columns:
        df = df[df["_drop_noise"] != True].drop(columns=["_drop_noise"])

    df["published_at"] = df["published_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df.attrs["errors"] = errors
    return df.reset_index(drop=True)
