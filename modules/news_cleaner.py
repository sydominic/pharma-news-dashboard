from __future__ import annotations

import html
import re
from io import BytesIO
from pathlib import Path
from typing import Iterable, List

import pandas as pd
from bs4 import BeautifulSoup

from .classifier import CATEGORY_ORDER, classify_article, classify_article_details
from .article_enricher import summarize_article

STANDARD_COLUMNS: List[str] = [
    "uid", "published_at", "date", "time", "source", "category", "keywords", "importance", "qa_flag",
    "title", "summary", "article_summary", "article_text", "sub_tags", "classification_reason", "classification_score",
    "body_fetch_status", "link", "rss_query_name", "rss_query", "collected_at"
]

TEXT_COLUMNS = [c for c in STANDARD_COLUMNS if c != "qa_flag"]
VALID_CATEGORIES = set(CATEGORY_ORDER + ["기타"])
NULL_LIKE = {"", "nan", "none", "nat", "null", "na", "n/a", "<na>"}
LINK_CANDIDATE_COLUMNS = ["link", "url", "article_url", "google_link", "rss_link", "source_url", "article_link", "origin_link"]


def ensure_data_dir(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def clean_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in NULL_LIKE:
        return ""
    for _ in range(3):
        new_text = html.unescape(text)
        if new_text == text:
            break
        text = new_text
    if "<" in text and ">" in text:
        try:
            text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
        except Exception:
            pass
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = text.replace("원문 열기 ↗", " ").replace("중요도 nan", " ").replace("nan", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if text.lower() in NULL_LIKE:
        return ""
    return text


def clean_link(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if not text or text.lower() in NULL_LIKE:
        return ""
    for _ in range(3):
        new_text = html.unescape(text)
        if new_text == text:
            break
        text = new_text
    if "<" in text and ">" in text:
        try:
            soup = BeautifulSoup(text, "html.parser")
            a = soup.find("a", href=True)
            if a and a.get("href"):
                text = str(a.get("href")).strip()
        except Exception:
            pass
    match = re.search(r"https?://[^\s\'\"<>]+", text)
    if match:
        return match.group(0).strip().rstrip(".,);]")
    return ""


def recover_link_from_candidates(row: pd.Series) -> str:
    for col in LINK_CANDIDATE_COLUMNS:
        if col in row.index:
            link = clean_link(row.get(col, ""))
            if link:
                return link
    return ""


def clean_title(value: object) -> str:
    text = clean_text(value)
    text = re.sub(r"\s+-\s+Google 뉴스$", "", text)
    return text


def clean_summary(value: object) -> str:
    raw = "" if value is None else str(value)
    bad_markers = ["news-card", "open-link", "class=", "border-left", "원문 열기", "<div", "</div>"]
    if any(marker in raw for marker in bad_markers):
        return ""
    text = clean_text(value)
    if any(marker in text for marker in bad_markers):
        return ""
    if text.lower() in NULL_LIKE:
        return ""
    return text[:400]


def clean_article_text(value: object) -> str:
    text = clean_text(value)
    return text[:6000]


def clean_article_summary(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in NULL_LIKE:
        return ""
    for _ in range(3):
        new_text = html.unescape(text)
        if new_text == text:
            break
        text = new_text
    if "<" in text and ">" in text:
        try:
            text = BeautifulSoup(text, "html.parser").get_text("\n", strip=True)
        except Exception:
            pass
    text = re.sub(r"https?://\S+", " ", text)
    lines = []
    for line in re.split(r"[\r\n]+", text):
        line = re.sub(r"\s+", " ", line).strip()
        if line and line.lower() not in NULL_LIKE:
            lines.append(line)
    return "\n".join(lines)[:1200]


def normalize_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    try:
        if pd.isna(value):
            return False
    except Exception:
        pass
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y", "중간", "높음"}


def make_empty_frame() -> pd.DataFrame:
    out = pd.DataFrame(columns=STANDARD_COLUMNS)
    out["qa_flag"] = pd.Series(dtype="bool")
    return out


def repair_and_reclassify(df: pd.DataFrame, force: bool = False) -> pd.DataFrame:
    """RSS/CSV 데이터를 표준 컬럼으로 정규화한다.

    v1.14 안정화 핵심:
    - 보관정책/retention 파이프라인 제거
    - 기존 DataFrame에 부분 대입하지 않고 row dict를 새로 구성
    - string dtype 컬럼에 bool/datetime 값을 넣는 구조 제거
    """
    if df is None or df.empty:
        return make_empty_frame()

    records = []
    input_df = df.copy()

    for _, row in input_df.iterrows():
        title = clean_title(row.get("title", ""))
        summary = clean_summary(row.get("summary", ""))
        article_text = clean_article_text(row.get("article_text", ""))
        article_summary = clean_article_summary(row.get("article_summary", ""))
        body_fetch_status = clean_text(row.get("body_fetch_status", ""))
        source = clean_text(row.get("source", ""))
        rss_query_name = clean_text(row.get("rss_query_name", ""))
        rss_query = clean_text(row.get("rss_query", ""))
        collected_at = clean_text(row.get("collected_at", ""))
        link = recover_link_from_candidates(row)

        # Existing caches may not yet have generated summaries. Create a safe 3~5 line fallback from RSS/body.
        if not article_summary:
            article_summary = summarize_article(title, summary, article_text, max_lines=4)
        if not body_fetch_status:
            body_fetch_status = "본문수집성공" if article_text else "RSS요약사용"

        category = clean_text(row.get("category", ""))
        keywords = clean_text(row.get("keywords", ""))
        importance = clean_text(row.get("importance", ""))
        sub_tags = clean_text(row.get("sub_tags", ""))
        classification_reason = clean_text(row.get("classification_reason", ""))
        classification_score = clean_text(row.get("classification_score", ""))
        qa_flag = normalize_bool(row.get("qa_flag", False))

        needs_cls = (
            force
            or category not in VALID_CATEGORIES
            or category == "기타"
            or not keywords
            or importance not in {"높음", "중간", "일반"}
            or not sub_tags
            or not classification_reason
            or not classification_score
        )
        if needs_cls:
            cls = classify_article_details(title, summary, article_text=article_text, source=source, rss_query=rss_query, article_summary=article_summary)
            category = str(cls.get("category", "산업/경영"))
            keywords = str(cls.get("keywords", ""))
            importance = str(cls.get("importance", "일반"))
            qa_flag = bool(cls.get("qa_flag", False))
            sub_tags = str(cls.get("sub_tags", ""))
            classification_reason = str(cls.get("classification_reason", ""))
            classification_score = str(cls.get("classification_score", ""))

        if clean_text(category) not in VALID_CATEGORIES:
            category = "산업/경영"
        if clean_text(importance) not in {"높음", "중간", "일반"}:
            importance = "일반"
        keywords = clean_text(keywords)

        published_dt = pd.to_datetime(row.get("published_at", ""), errors="coerce")
        if pd.isna(published_dt):
            published_dt = pd.Timestamp.now()
        published_at = published_dt.strftime("%Y-%m-%d %H:%M:%S")
        date_value = published_dt.strftime("%Y-%m-%d")
        time_value = published_dt.strftime("%H:%M")

        uid = clean_text(row.get("uid", ""))
        if not uid:
            uid = f"{source}|{published_at}|{title}".lower()

        records.append({
            "uid": uid,
            "published_at": published_at,
            "date": date_value,
            "time": time_value,
            "source": source,
            "category": category,
            "keywords": keywords,
            "importance": importance,
            "qa_flag": bool(qa_flag),
            "title": title,
            "summary": summary,
            "article_summary": article_summary,
            "article_text": article_text,
            "sub_tags": sub_tags,
            "classification_reason": classification_reason,
            "classification_score": classification_score,
            "body_fetch_status": body_fetch_status,
            "link": link,
            "rss_query_name": rss_query_name,
            "rss_query": rss_query,
            "collected_at": collected_at,
        })

    out = pd.DataFrame.from_records(records, columns=STANDARD_COLUMNS)
    if out.empty:
        return make_empty_frame()

    for col in TEXT_COLUMNS:
        out[col] = out[col].fillna("").astype("object")
    out["qa_flag"] = out["qa_flag"].apply(normalize_bool).astype("bool")
    out = out.drop_duplicates(subset=["uid"], keep="first")
    return out.sort_values("published_at", ascending=False).reset_index(drop=True)


def normalize_and_classify(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return make_empty_frame()
    return repair_and_reclassify(df, force=True)


def load_news(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return make_empty_frame()
    df = pd.read_csv(p, encoding="utf-8-sig", dtype="object")
    return repair_and_reclassify(df, force=False)


def save_news(df: pd.DataFrame, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    repaired = repair_and_reclassify(df, force=False)
    repaired.to_csv(p, index=False, encoding="utf-8-sig")


def merge_existing(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    frames = []
    if existing is not None and not existing.empty:
        frames.append(existing)
    if new is not None and not new.empty:
        frames.append(new)
    if not frames:
        return make_empty_frame()

    merged = pd.concat(frames, ignore_index=True).astype("object")
    merged = repair_and_reclassify(merged, force=False)

    merged["_has_link"] = merged["link"].apply(lambda x: bool(clean_link(x)))
    merged["published_at_dt"] = pd.to_datetime(merged["published_at"], errors="coerce")
    merged = merged.sort_values(["uid", "_has_link", "published_at_dt"], ascending=[True, False, False])
    merged = merged.drop_duplicates(subset=["uid"], keep="first")
    merged = merged.sort_values("published_at_dt", ascending=False).drop(columns=["published_at_dt", "_has_link"])
    return merged.reset_index(drop=True)


def filter_news(df: pd.DataFrame, start_date, end_date, categories: Iterable[str], sources: Iterable[str], keyword: str, importances: Iterable[str] | None = None) -> pd.DataFrame:
    if df is None or df.empty:
        return make_empty_frame()
    work = repair_and_reclassify(df, force=False)
    work["published_at_dt"] = pd.to_datetime(work["published_at"], errors="coerce")

    if start_date is not None:
        work = work[work["published_at_dt"].dt.date >= start_date]
    if end_date is not None:
        work = work[work["published_at_dt"].dt.date <= end_date]

    categories = [x for x in categories if x and x != "전체"]
    if categories:
        work = work[work["category"].isin(categories)]

    sources = [x for x in sources if x and x != "전체"]
    if sources:
        work = work[work["source"].isin(sources)]

    importances = [x for x in (importances or []) if x and x != "전체"]
    if importances:
        work = work[work["importance"].isin(importances)]

    keyword = (keyword or "").strip().lower()
    if keyword:
        hay = (
            work["title"].fillna("").astype(str) + " " +
            work["summary"].fillna("").astype(str) + " " +
            work.get("article_summary", pd.Series([""] * len(work))).fillna("").astype(str) + " " +
            work.get("article_text", pd.Series([""] * len(work))).fillna("").astype(str) + " " +
            work["keywords"].fillna("").astype(str) + " " +
            work.get("sub_tags", pd.Series([""] * len(work))).fillna("").astype(str) + " " +
            work["source"].fillna("").astype(str)
        ).str.lower()
        work = work[hay.str.contains(keyword, regex=False, na=False)]

    return work.drop(columns=["published_at_dt"], errors="ignore").reset_index(drop=True)


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    export_df = repair_and_reclassify(df, force=False)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name="news", index=False)
        ws = writer.sheets["news"]
        for col_cells in ws.columns:
            values = [str(cell.value) if cell.value is not None else "" for cell in col_cells]
            max_len = min(max([len(v) for v in values] + [10]) + 2, 60)
            ws.column_dimensions[col_cells[0].column_letter].width = max_len
    return output.getvalue()


def sample_news() -> pd.DataFrame:
    sample_rows = [
        {
            "uid": "sample01", "published_at": "2026-05-12 09:30:00", "date": "2026-05-12", "time": "09:30",
            "source": "데일리팜", "title": "식약처, 의약품 GMP 실태조사 결과 공개",
            "summary": "샘플 데이터입니다. RSS 수집 후 실제 기사로 대체됩니다.",
            "link": "", "rss_query_name": "sample", "rss_query": "", "collected_at": "",
        },
        {
            "uid": "sample02", "published_at": "2026-05-12 08:50:00", "date": "2026-05-12", "time": "08:50",
            "source": "히트뉴스", "title": "국내 제약사, 신약 임상 3상 승인",
            "summary": "샘플 데이터입니다.", "link": "", "rss_query_name": "sample", "rss_query": "", "collected_at": "",
        },
        {
            "uid": "sample03", "published_at": "2026-05-11 17:40:00", "date": "2026-05-11", "time": "17:40",
            "source": "팜뉴스", "title": "일부 의약품 회수 공지, 제조번호 확인 필요",
            "summary": "샘플 데이터입니다.", "link": "", "rss_query_name": "sample", "rss_query": "", "collected_at": "",
        },
        {
            "uid": "sample04", "published_at": "2026-05-11 14:15:00", "date": "2026-05-11", "time": "14:15",
            "source": "바이오스펙테이터", "title": "FDA, 바이오의약품 허가 가이드라인 개정",
            "summary": "샘플 데이터입니다.", "link": "", "rss_query_name": "sample", "rss_query": "", "collected_at": "",
        },
    ]
    df = pd.DataFrame(sample_rows)
    return repair_and_reclassify(df, force=True)
