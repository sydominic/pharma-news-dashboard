from __future__ import annotations

import html
import re
from io import BytesIO
from pathlib import Path
from typing import Iterable, List

import pandas as pd
from bs4 import BeautifulSoup

from .classifier import CATEGORY_ORDER, classify_article

STANDARD_COLUMNS: List[str] = [
    "uid", "published_at", "date", "time", "source", "category", "keywords", "importance", "qa_flag",
    "title", "summary", "link", "rss_query_name", "rss_query", "collected_at"
]

VALID_CATEGORIES = set(CATEGORY_ORDER + ["기타"])
NULL_LIKE = {"", "nan", "none", "nat", "null", "na", "n/a"}
LINK_CANDIDATE_COLUMNS = ["link", "url", "article_url", "google_link", "rss_link", "source_url", "article_link", "origin_link"]


def ensure_data_dir(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in NULL_LIKE:
        return ""
    for _ in range(3):
        new_text = html.unescape(text)
        if new_text == text:
            break
        text = new_text
    # Google News summary나 이전 버전 CSV에 HTML 조각이 들어간 경우 제거
    if "<" in text and ">" in text:
        text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = text.replace("원문 열기 ↗", " ").replace("중요도 nan", " ").replace("nan", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if text.lower() in NULL_LIKE:
        return ""
    return text


def clean_link(value: object) -> str:
    """URL은 일반 텍스트 정리와 다르게 보존한다.

    v1.9까지는 link 컬럼에도 clean_text()를 적용하면서
    https://... 문자열이 제거되어 원문 버튼이 생성되지 않았다.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() in NULL_LIKE:
        return ""
    for _ in range(3):
        new_text = html.unescape(text)
        if new_text == text:
            break
        text = new_text
    if "<" in text and ">" in text:
        soup = BeautifulSoup(text, "html.parser")
        a = soup.find("a", href=True)
        if a and a.get("href"):
            text = str(a.get("href")).strip()
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
    # Google News title에 이미 붙는 끝부분 언론사명은 유지해도 되지만, 너무 긴 반복만 완화
    text = re.sub(r"\s+-\s+Google 뉴스$", "", text)
    return text


def clean_summary(value: object) -> str:
    raw = "" if value is None else str(value)
    bad_markers = ["news-card", "open-link", "class=", "border-left", "원문 열기", "<div", "</div>"]
    if any(marker in raw for marker in bad_markers):
        return ""
    text = clean_text(value)
    # v1.1 화면 HTML이 저장/표시된 흔적이 있으면 요약으로 쓰지 않음
    if any(marker in text for marker in bad_markers):
        return ""
    if text.lower() in NULL_LIKE:
        return ""
    return text[:400]


def normalize_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y", "중간", "높음"}


def needs_reclassify(row: pd.Series) -> bool:
    category = clean_text(row.get("category", ""))
    keywords = clean_text(row.get("keywords", ""))
    importance = clean_text(row.get("importance", ""))
    if category not in VALID_CATEGORIES:
        return True
    if category in {"기타"}:
        return True
    if not keywords:
        return True
    if importance not in {"높음", "중간", "일반"}:
        return True
    return False


def repair_and_reclassify(df: pd.DataFrame, force: bool = False) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    work = df.copy()
    for col in STANDARD_COLUMNS:
        if col not in work.columns:
            work[col] = ""

    # link는 URL 자체를 보존해야 하므로 clean_text()가 아니라 clean_link()로 처리한다.
    # 기존/외부 CSV에서 url, article_url 등 다른 컬럼명으로 들어온 경우도 link로 복구한다.
    work["link"] = work.apply(recover_link_from_candidates, axis=1)

    for col in ["title", "source", "rss_query_name", "rss_query", "collected_at"]:
        work[col] = work[col].apply(clean_text)
    work["title"] = work["title"].apply(clean_title)
    work["summary"] = work["summary"].apply(clean_summary)

    # category/keywords/importance의 nan/None 문자열 정리
    for col in ["category", "keywords", "importance"]:
        work[col] = work[col].apply(clean_text)

    # v1.1에서 이미 누적된 None/nan/기타를 제목+요약 기준으로 재분류
    mask = work.apply(needs_reclassify, axis=1) if not force else pd.Series([True] * len(work), index=work.index)
    if mask.any():
        classified = work.loc[mask].apply(lambda r: classify_article(r.get("title", ""), r.get("summary", "")), axis=1)
        work.loc[mask, "category"] = [x[0] for x in classified]
        work.loc[mask, "keywords"] = [x[1] for x in classified]
        work.loc[mask, "importance"] = [x[2] for x in classified]
        work.loc[mask, "qa_flag"] = [bool(x[3]) for x in classified]

    # 최종 보정: 카테고리 공란/None은 산업/경영으로 보냄
    work["category"] = work["category"].apply(lambda x: x if clean_text(x) in VALID_CATEGORIES else "산업/경영")
    work["importance"] = work["importance"].apply(lambda x: x if clean_text(x) in {"높음", "중간", "일반"} else "일반")
    work["qa_flag"] = work["qa_flag"].apply(normalize_bool)

    work["published_at"] = pd.to_datetime(work["published_at"], errors="coerce")
    work["published_at"] = work["published_at"].fillna(pd.Timestamp.now())
    work["date"] = work["published_at"].dt.strftime("%Y-%m-%d")
    work["time"] = work["published_at"].dt.strftime("%H:%M")
    work["published_at"] = work["published_at"].dt.strftime("%Y-%m-%d %H:%M:%S")

    if "uid" not in work.columns or work["uid"].fillna("").astype(str).str.strip().eq("").any():
        work["uid"] = work.apply(lambda r: f"{r['source']}|{r['published_at']}|{r['title']}".lower(), axis=1)

    work = work[STANDARD_COLUMNS].drop_duplicates(subset=["uid"], keep="first")
    return work.sort_values("published_at", ascending=False).reset_index(drop=True)


def normalize_and_classify(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=STANDARD_COLUMNS)
    return repair_and_reclassify(df, force=True)


def load_news(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=STANDARD_COLUMNS)
    df = pd.read_csv(p, encoding="utf-8-sig")
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
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    merged = pd.concat(frames, ignore_index=True)
    for col in STANDARD_COLUMNS:
        if col not in merged.columns:
            merged[col] = ""
    merged = repair_and_reclassify(merged, force=False)

    # 같은 기사(uid)가 기존 CSV에는 link 공란, 신규 수집에는 link 보유 상태로 들어올 수 있다.
    # 이 경우 원문 버튼 복구를 위해 link가 있는 행을 우선 보존한다.
    merged["_has_link"] = merged["link"].apply(lambda x: bool(clean_link(x)))
    merged["published_at_dt"] = pd.to_datetime(merged["published_at"], errors="coerce")
    merged = merged.sort_values(["uid", "_has_link", "published_at_dt"], ascending=[True, False, False])
    merged = merged.drop_duplicates(subset=["uid"], keep="first")
    merged = merged.sort_values("published_at_dt", ascending=False).drop(columns=["published_at_dt", "_has_link"])
    return merged.reset_index(drop=True)


def filter_news(df: pd.DataFrame, start_date, end_date, categories: Iterable[str], sources: Iterable[str], keyword: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=STANDARD_COLUMNS)
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

    keyword = (keyword or "").strip().lower()
    if keyword:
        hay = (
            work["title"].fillna("").astype(str) + " " +
            work["summary"].fillna("").astype(str) + " " +
            work["keywords"].fillna("").astype(str) + " " +
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
    rows = [
        ["sample01", "2026-05-12 09:30:00", "2026-05-12", "09:30", "데일리팜", "식약처/규제", "식약처, GMP", "중간", True, "식약처, 의약품 GMP 실태조사 결과 공개", "샘플 데이터입니다. RSS 수집 후 실제 기사로 대체됩니다.", "", "sample", "", ""],
        ["sample02", "2026-05-12 08:50:00", "2026-05-12", "08:50", "히트뉴스", "허가/임상", "허가, 임상", "일반", False, "국내 제약사, 신약 임상 3상 승인", "샘플 데이터입니다.", "", "sample", "", ""],
        ["sample03", "2026-05-11 17:40:00", "2026-05-11", "17:40", "팜뉴스", "회수/처분", "회수, 부적합", "높음", True, "일부 의약품 회수 공지, 제조번호 확인 필요", "샘플 데이터입니다.", "", "sample", "", ""],
        ["sample04", "2026-05-11 14:15:00", "2026-05-11", "14:15", "바이오스펙테이터", "해외규제", "FDA, EMA", "중간", True, "FDA, 바이오의약품 허가 가이드라인 개정", "샘플 데이터입니다.", "", "sample", "", ""],
    ]
    return pd.DataFrame(rows, columns=STANDARD_COLUMNS)
