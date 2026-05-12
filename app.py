from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st

from modules.classifier import CATEGORY_ORDER, category_palette
from modules.news_cleaner import (
    STANDARD_COLUMNS,
    filter_news,
    load_news,
    merge_existing,
    normalize_and_classify,
    repair_and_reclassify,
    sample_news,
    save_news,
    to_excel_bytes,
)
from modules.policy_links import extract_policy_articles, mfds_board_links, mfds_board_home_links
from modules.rss_collector import collect_google_news, load_rss_config
from modules.ui_components import article_card, esc, header, inject_css, kpi_card, keyword_pills, section_title, timeline_item, title_with_link

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = DATA_DIR / "rss_sources.json"
RAW_PATH = DATA_DIR / "news_raw.csv"
CLEAN_PATH = DATA_DIR / "news_clean.csv"
APP_VERSION = "v1.25"

st.set_page_config(page_title="제약뉴스 RSS 대시보드", page_icon="📰", layout="wide", initial_sidebar_state="collapsed")
inject_css()

IMPORTANCE_ORDER = {"높음": 3, "중간": 2, "일반": 1}


def _read_app_password() -> str:
    """Streamlit Cloud secrets에서 APP_PASSWORD를 읽습니다. 값이 없으면 공개 모드로 실행합니다."""
    try:
        value = st.secrets.get("APP_PASSWORD", "")
    except Exception:
        value = ""
    return str(value or "").strip()


def require_password_if_configured() -> None:
    """APP_PASSWORD가 설정된 경우에만 간단한 접속 비밀번호를 요구합니다."""
    app_password = _read_app_password()
    if not app_password:
        return
    if st.session_state.get("pharma_news_auth_ok"):
        return

    header("제약뉴스 RSS 대시보드", "온라인 접속 보호가 설정되어 있습니다.")
    st.info("관리자가 설정한 접속 비밀번호를 입력해 주세요.")
    with st.form("password_form"):
        entered = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("접속")
    if submitted:
        if entered == app_password:
            st.session_state["pharma_news_auth_ok"] = True
            st.rerun()
        else:
            st.error("비밀번호가 맞지 않습니다.")
    st.stop()


KEYWORD_EXCLUDE_EXACT = {
    # 언론사/소스명
    "데일리팜", "히트뉴스", "팜뉴스", "메디파나", "메디파나뉴스", "약업신문", "약업닷컴", "한국의약통신", "헬스코리아뉴스", "약사공론",
    "의학신문", "바이오스펙테이터", "메디칼타임즈", "코메디닷컴", "이데일리", "연합뉴스", "매일경제", "한국경제", "서울경제",
    # 회사명/브랜드명: 키워드 트렌드에서 제외
    "한올바이오파마", "한올", "셀트리온", "삼성바이오", "삼성바이오로직스", "삼성바이오에피스", "유한양행", "종근당", "대웅", "대웅제약",
    "보령", "한미약품", "녹십자", "GC녹십자", "HK이노엔", "동아에스티", "일동제약", "JW중외제약", "휴온스", "동국제약",
    "SK바이오팜", "SK바이오사이언스", "제넥신", "에스티팜", "브릿지바이오", "온코닉테라퓨틱스", "카나프", "목암연구소",
    # 사람명/직책명/조직 내 역할명
    "이상혁", "대표", "대표이사", "회장", "부회장", "사장", "부사장", "전무", "상무", "이사", "본부장", "부장", "팀장", "연구소장",
    "교수", "원장", "국장", "처장", "위원장", "CEO", "CFO", "CMO", "CTO", "포트폴리오기획본부장",
    # 기사성/행사성 일반 단어
    "전국", "학술", "성공사례", "100주년", "기자", "단독", "포커스", "인터뷰", "오늘", "내일",
}

KEYWORD_KEEP = {
    "식약처", "GMP", "허가", "임상", "회수", "행정처분", "FDA", "EMA", "PMDA", "품질", "데이터완전성", "무균", "바이오시밀러", "신약",
    "기술수출", "CDMO", "약가", "급여", "투자", "공장", "수출", "불순물", "오염", "밸리데이션", "PIC/S", "ICH", "R&D",
    "제약", "바이오", "글로벌", "공급망", "치료제", "가이드라인", "안내서", "행정예고", "고시", "약전", "제도개선", "입법예고",
    "정책", "규제", "허가심사", "민원인안내서", "공무원지침서", "의약품", "바이오의약품", "희귀질환", "항암제", "면역항암제"
}

COMPANY_SUFFIXES = (
    "제약", "약품", "바이오", "바이오파마", "바이오로직스", "바이오텍", "테라퓨틱스", "파마", "팜", "헬스케어", "메디텍", "메디칼", "메디컬"
)
TITLE_SUFFIXES = ("대표", "회장", "사장", "부사장", "전무", "상무", "이사", "본부장", "부장", "팀장", "소장", "교수", "원장", "국장", "처장", "위원장")


def is_noise_keyword(keyword: object) -> bool:
    kw = str(keyword).strip()
    if not kw or kw.lower() in {"nan", "none", "nat", "null"}:
        return True
    if kw in KEYWORD_KEEP:
        return False
    if kw in KEYWORD_EXCLUDE_EXACT:
        return True
    # 직책·직함성 단어 또는 회사명으로 보이는 고유명사 제외
    if any(kw.endswith(suf) for suf in TITLE_SUFFIXES) and len(kw) >= 3:
        return True
    if any(kw.endswith(suf) for suf in COMPANY_SUFFIXES) and len(kw) >= 4:
        return True
    if any(s in kw for s in ["주식회사", "㈜", "(주)", "파트너스", "홀딩스"]):
        return True
    # 단일 기사 제목에서 잡히는 사람 이름 형태를 보수적으로 제외: 2~4자 한글 + 보존키워드 아님
    # 단, 규제/품질/임상 핵심어는 KEYWORD_KEEP에서 먼저 통과된다.
    if kw in {"김정훈", "이정훈", "박정훈", "김현수", "이현수", "박현수", "김민수", "이민수", "박민수"}:
        return True
    return False


def count_keywords(df: pd.DataFrame) -> Counter:
    counter: Counter = Counter()
    if df.empty or "keywords" not in df.columns:
        return counter
    for value in df["keywords"].fillna(""):
        for keyword in str(value).split(","):
            keyword = keyword.strip()
            if keyword and not is_noise_keyword(keyword):
                counter[keyword] += 1
    return counter


def collect_and_save(start_date=None, end_date=None, max_items_per_query: int | None = None) -> Tuple[pd.DataFrame, List[str], int]:
    raw = collect_google_news(CONFIG_PATH, start_date=start_date, end_date=end_date, max_items_per_query=max_items_per_query)
    errors = raw.attrs.get("errors", []) if hasattr(raw, "attrs") else []
    if not raw.empty:
        raw.to_csv(RAW_PATH, index=False, encoding="utf-8-sig")
    clean = normalize_and_classify(raw)
    existing = load_news(CLEAN_PATH)
    before = len(existing)
    merged = merge_existing(existing, clean)
    save_news(merged, CLEAN_PATH)
    added = max(len(merged) - before, 0)
    return merged, errors, added


def load_or_collect_initial() -> pd.DataFrame:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = load_news(CLEAN_PATH)
    if not df.empty:
        # v1.4 분류체계(정책/가이드라인 포함)로 기존 누적자료를 다시 보정
        df = repair_and_reclassify(df, force=True)
        save_news(df, CLEAN_PATH)
        return df
    try:
        with st.spinner("최초 실행: 최근 7일 Google News RSS에서 기사 수집 중입니다..."):
            today = date.today()
            df, errors, _ = collect_and_save(start_date=today - timedelta(days=6), end_date=today)
        if errors:
            st.warning("일부 RSS 검색식에서 수집 오류가 있었습니다. 수집된 데이터는 정상 표시합니다.")
        if not df.empty:
            return df
    except Exception as exc:
        st.warning(f"RSS 최초 수집에 실패했습니다. 화면 확인용 샘플 데이터를 표시합니다. 오류: {exc}")
    return sample_news()


def prepare_display_df(df: pd.DataFrame) -> pd.DataFrame:
    work = repair_and_reclassify(df, force=False).copy()
    for col in STANDARD_COLUMNS:
        if col not in work.columns:
            work[col] = ""
    work["published_at_dt"] = pd.to_datetime(work["published_at"], errors="coerce")
    work = work.sort_values("published_at_dt", ascending=False)
    work["published_at"] = work["published_at_dt"].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
    work["date"] = work["published_at_dt"].dt.strftime("%Y-%m-%d").fillna("")
    work["time"] = work["published_at_dt"].dt.strftime("%H:%M").fillna("")
    for c in ["category", "keywords", "importance", "summary", "source", "title", "link"]:
        if c in work.columns:
            work[c] = work[c].fillna("").astype(str).replace({"nan": "", "None": ""})
    work["category"] = work["category"].replace("", "산업/경영")
    work["importance"] = work["importance"].replace("", "일반")
    return work.drop(columns=["published_at_dt"], errors="ignore").reset_index(drop=True)


def category_counts(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["category", "count"])
    order = CATEGORY_ORDER + ["기타"]
    counts = df["category"].fillna("기타").value_counts().rename_axis("category").reset_index(name="count")
    counts["sort"] = counts["category"].apply(lambda x: order.index(x) if x in order else 999)
    return counts.sort_values("sort").drop(columns=["sort"])


def render_category_pie(df: pd.DataFrame, title: str = "카테고리 분포") -> None:
    counts = category_counts(df)
    if counts.empty:
        st.info("표시할 카테고리 데이터가 없습니다.")
        return
    fig = px.pie(counts, values="count", names="category", hole=0.58, title=title, color="category", color_discrete_map=category_palette())
    fig.update_layout(height=330, margin=dict(l=10, r=10, t=46, b=10), legend_title_text="")
    fig.update_traces(textinfo="none", hovertemplate="%{label}: %{value}건 (%{percent})<extra></extra>")
    st.plotly_chart(fig, use_container_width=True)


def category_ratio_table(df: pd.DataFrame) -> pd.DataFrame:
    counts = category_counts(df)
    if counts.empty:
        return pd.DataFrame(columns=["카테고리", "기사 수", "비중"])
    total = counts["count"].sum()
    counts["ratio"] = counts["count"].apply(lambda x: f"{(x/total*100):.1f}%" if total else "0.0%")
    return counts.rename(columns={"category": "카테고리", "count": "기사 수", "ratio": "비중"})


def render_keyword_bar(df: pd.DataFrame, title: str = "키워드 TOP 10") -> None:
    counter = count_keywords(df)
    if not counter:
        st.info("표시할 키워드 데이터가 없습니다.")
        return
    top = pd.DataFrame(counter.most_common(10), columns=["keyword", "count"])
    fig = px.bar(top.sort_values("count"), x="count", y="keyword", orientation="h", title=title, text="count")
    fig.update_layout(height=330, margin=dict(l=10, r=10, t=46, b=10), xaxis_title="기사 수", yaxis_title="")
    fig.update_traces(marker_color="#0065d8", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)


def category_trend(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["date", "category", "count"])
    work = df.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work["category"] = work["category"].fillna("산업/경영").astype(str).replace({"": "산업/경영", "nan": "산업/경영", "None": "산업/경영"})
    trend = work.dropna(subset=["date"]).groupby(["date", "category"], as_index=False).size().rename(columns={"size": "count"})
    return trend.sort_values("date")


def render_category_trend(df: pd.DataFrame) -> None:
    trend = category_trend(df)
    if trend.empty:
        st.info("표시할 카테고리 추이 데이터가 없습니다.")
        return
    fig = px.line(
        trend,
        x="date",
        y="count",
        color="category",
        markers=True,
        title="카테고리 추이",
        color_discrete_map=category_palette(),
    )
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=46, b=10), xaxis_title="일자", yaxis_title="기사 수", legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)


def category_top_table(df: pd.DataFrame, limit: int = 7) -> pd.DataFrame:
    counts = category_counts(df)
    if counts.empty:
        return pd.DataFrame(columns=["카테고리", "기사 수", "비중"])
    total = counts["count"].sum()
    out = counts.sort_values("count", ascending=False).head(limit).copy()
    out["ratio"] = out["count"].apply(lambda x: f"{(x / total * 100):.1f}%" if total else "0.0%")
    return out.rename(columns={"category": "카테고리", "count": "기사 수", "ratio": "비중"})


def generate_issue_summary(df: pd.DataFrame) -> List[str]:
    if df is None or df.empty:
        return ["현재 조회 조건에 해당하는 기사가 없습니다."]
    total = len(df)
    high = int((df["importance"] == "높음").sum()) if "importance" in df.columns else 0
    policy = int((df["category"] == "정책/가이드라인").sum()) if "category" in df.columns else 0
    recall = int((df["category"] == "회수/처분").sum()) if "category" in df.columns else 0
    gmp = int((df["category"] == "GMP/품질").sum()) if "category" in df.columns else 0
    overseas = int((df["category"] == "해외규제").sum()) if "category" in df.columns else 0
    top_cat = category_top_table(df, limit=1)
    lines = [f"현재 조회 조건 기준 총 {total:,}건의 기사가 수집·분류되었습니다."]
    if not top_cat.empty:
        lines.append(f"가장 많이 감지된 카테고리는 {top_cat.iloc[0]['카테고리']}이며, {top_cat.iloc[0]['기사 수']}건({top_cat.iloc[0]['비중']})입니다.")
    if high:
        lines.append(f"중요도 높음 기사가 {high}건 있습니다. 회수·처분, 품질위험 또는 안전성 관련 신호를 우선 확인하는 것이 좋습니다.")
    if policy:
        lines.append(f"정책/가이드라인성 기사가 {policy}건 감지되었습니다. 5탭의 규제기관 정책에서 원문과 공식 게시판을 함께 확인할 수 있습니다.")
    if recall:
        lines.append(f"회수/처분 관련 기사가 {recall}건 있습니다. 제조번호, 사유, 조치 범위 확인이 필요할 수 있습니다.")
    if gmp:
        lines.append(f"GMP/품질 관련 기사가 {gmp}건 있습니다. 실태조사, 데이터완전성, 제조·품질관리 이슈 여부를 확인하십시오.")
    if overseas:
        lines.append(f"해외규제 관련 기사가 {overseas}건 있습니다. FDA, EMA 등 해외 규제 변화 여부를 확인하십시오.")
    return lines[:6]


ISSUE_STOPWORDS = {
    "제약", "바이오", "의약품", "신약", "국내", "글로벌", "관련", "발표", "공개", "추진", "강화", "확대", "시장",
    "기준", "개선", "방안", "위한", "대한", "이번", "업계", "기업", "기술", "플랫폼", "치료제", "헬스케어",
    "뉴스", "포커스", "단독", "인터뷰", "기자", "종합", "속보", "개최", "참여", "지원", "선정", "성과",
}


def clean_issue_title(title: object) -> str:
    txt = str(title or "")
    txt = re.sub(r"\[[^\]]+\]", " ", txt)
    txt = re.sub(r"\([^\)]*\)", " ", txt)
    txt = re.sub(r"\s+-\s+[^-]{2,30}$", " ", txt)
    txt = re.sub(r"[\"'‘’“”…·,.:;!?/\\|]+", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def issue_tokens(title: object) -> set[str]:
    txt = clean_issue_title(title)
    tokens = re.findall(r"[가-힣A-Za-z0-9]{2,}", txt)
    out = []
    for token in tokens:
        t = token.strip()
        if len(t) < 2:
            continue
        if t in ISSUE_STOPWORDS:
            continue
        if re.fullmatch(r"\d+", t):
            continue
        out.append(t)
    return set(out[:12])


def issue_similarity(a_title: object, b_title: object) -> float:
    a_tokens = issue_tokens(a_title)
    b_tokens = issue_tokens(b_title)
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = len(a_tokens & b_tokens) / max(min(len(a_tokens), len(b_tokens)), 1)
    text_sim = SequenceMatcher(None, clean_issue_title(a_title), clean_issue_title(b_title)).ratio()
    return max(overlap, text_sim * 0.8)


def group_similar_issues(df: pd.DataFrame, max_groups: int = 8, threshold: float = 0.46) -> list[dict]:
    if df is None or df.empty:
        return []
    work = importance_articles(df).head(160).copy()
    groups: list[dict] = []
    for _, row in work.iterrows():
        title = str(row.get("title", ""))
        category = str(row.get("category", ""))
        if not title:
            continue
        placed = False
        for group in groups:
            if category != group["category"]:
                continue
            sim = issue_similarity(title, group["representative_title"])
            if sim >= threshold:
                group["rows"].append(row)
                group["sources"].add(str(row.get("source", "")))
                placed = True
                break
        if not placed:
            groups.append({
                "representative_title": title,
                "category": category,
                "rows": [row],
                "sources": {str(row.get("source", ""))},
            })
    groups = [g for g in groups if len(g["rows"]) >= 2]
    groups.sort(key=lambda g: (len(g["rows"]), len(g["sources"])), reverse=True)
    return groups[:max_groups]


def render_issue_groups(groups: list[dict]) -> None:
    if not groups:
        st.info("현재 조회 조건에서는 유사 이슈로 묶을 수 있는 기사가 충분하지 않습니다.")
        return
    html_parts = ["<div class='issue-group-wrap'>"]
    for group in groups:
        rows = group["rows"][:5]
        sources = sorted([s for s in group["sources"] if s])
        rep = rows[0]
        source_txt = ", ".join(sources[:5])
        html_parts.append("<div class='issue-group-card'>")
        html_parts.append(f"<div class='issue-group-head'><b>{esc(group['representative_title'])}</b><span>{len(group['rows'])}건 · {esc(group['category'])}</span></div>")
        html_parts.append(f"<div class='issue-group-meta'>언론사: {esc(source_txt) if source_txt else '확인 없음'}</div>")
        html_parts.append("<ul class='issue-list'>")
        for r in rows:
            title = esc(r.get("title", ""))
            source = esc(r.get("source", ""))
            link = esc(r.get("link", ""))
            if link:
                html_parts.append(f"<li><span>{source}</span> <a href='{link}' target='_blank' rel='noopener noreferrer'>{title} ↗</a></li>")
            else:
                html_parts.append(f"<li><span>{source}</span> {title}</li>")
        html_parts.append("</ul></div>")
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def build_weekly_report(df: pd.DataFrame, issue_groups: list[dict], start_date, end_date) -> bytes:
    lines = []
    lines.append("# 제약뉴스 주간 모니터링 리포트")
    lines.append("")
    lines.append(f"- 생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"- 조회기간: {start_date} ~ {end_date}")
    lines.append(f"- 전체 기사 수: {len(df):,}건")
    lines.append("")
    lines.append("## 1. 중요 이슈 요약")
    for line in generate_issue_summary(df):
        lines.append(f"- {line}")
    lines.append("")
    lines.append("## 2. 카테고리 TOP 7")
    ctop = category_top_table(df, limit=7)
    if ctop.empty:
        lines.append("- 표시할 카테고리 데이터가 없습니다.")
    else:
        for _, row in ctop.iterrows():
            lines.append(f"- {row['카테고리']}: {row['기사 수']}건 ({row['비중']})")
    lines.append("")
    lines.append("## 3. 유사 이슈 묶음")
    if not issue_groups:
        lines.append("- 유사 이슈로 묶인 기사가 없습니다.")
    else:
        for idx, group in enumerate(issue_groups, start=1):
            sources = ", ".join(sorted([s for s in group['sources'] if s]))
            lines.append(f"### {idx}. {group['representative_title']}")
            lines.append(f"- 카테고리: {group['category']}")
            lines.append(f"- 기사 수: {len(group['rows'])}건")
            lines.append(f"- 언론사: {sources}")
            for r in group['rows'][:5]:
                lines.append(f"  - {r.get('source','')}: {r.get('title','')} ({r.get('link','')})")
            lines.append("")
    lines.append("## 4. 주요 기사")
    for _, row in importance_articles(df).head(10).iterrows():
        lines.append(f"- [{row.get('category','')}/{row.get('importance','')}] {row.get('source','')} - {row.get('title','')} ({row.get('link','')})")
    lines.append("")
    lines.append("## 5. 정책/가이드라인 기사")
    policy_df = extract_policy_articles(df)
    if policy_df.empty:
        lines.append("- 정책/가이드라인성 기사가 감지되지 않았습니다.")
    else:
        for _, row in policy_df.head(10).iterrows():
            lines.append(f"- {row.get('source','')} - {row.get('title','')} ({row.get('link','')})")
    return "\n".join(lines).encode("utf-8-sig")


def category_keyword_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if df.empty:
        return pd.DataFrame(columns=["카테고리", "기사 수", "주요 키워드"])
    for category in CATEGORY_ORDER:
        sub = df[df["category"] == category]
        if sub.empty:
            continue
        counter = count_keywords(sub)
        top_keywords = ", ".join([f"{kw}({cnt})" for kw, cnt in counter.most_common(6)])
        rows.append({"카테고리": category, "기사 수": len(sub), "주요 키워드": top_keywords})
    return pd.DataFrame(rows)


def representative_articles(df: pd.DataFrame, limit: int = 5) -> pd.DataFrame:
    if df.empty:
        return df
    counter = count_keywords(df)
    top_keywords = [kw for kw, _ in counter.most_common(12)]
    work = df.copy()
    work["published_at_dt"] = pd.to_datetime(work["published_at"], errors="coerce")

    def kw_score(value: object) -> int:
        kws = [x.strip() for x in str(value).split(",") if x.strip()]
        return sum(1 for kw in kws if kw in top_keywords)

    work["_keyword_score"] = work["keywords"].apply(kw_score)
    work["_importance_score"] = work["importance"].map(IMPORTANCE_ORDER).fillna(1)
    work["_category_score"] = work["category"].apply(lambda x: 1 if x in ["회수/처분", "정책/가이드라인", "식약처/규제", "GMP/품질", "해외규제"] else 0)
    work["_rep_score"] = (work["_keyword_score"] * 3) + (work["_importance_score"] * 2) + work["_category_score"]
    return work.sort_values(["_rep_score", "published_at_dt"], ascending=[False, False]).drop(columns=["published_at_dt", "_keyword_score", "_importance_score", "_category_score", "_rep_score"], errors="ignore").head(limit)


def importance_articles(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    work["published_at_dt"] = pd.to_datetime(work["published_at"], errors="coerce")
    work["_importance_rank"] = work["importance"].map(IMPORTANCE_ORDER).fillna(1)
    return work.sort_values(["_importance_rank", "published_at_dt"], ascending=[False, False]).drop(columns=["published_at_dt", "_importance_rank"], errors="ignore")


def render_pretty_table(df: pd.DataFrame, columns: List[str], headers: List[str] | None = None, max_rows: int | None = None) -> None:
    """작은 요약표를 엑셀식 dataframe 대신 카드형 HTML 표로 표시합니다."""
    if df is None or df.empty:
        st.info("표시할 데이터가 없습니다.")
        return
    show = df.copy()
    if max_rows is not None:
        show = show.head(max_rows)
    headers = headers or columns
    html_parts = ["<div class='pretty-table-wrap'><table class='pretty-table'><thead><tr>"]
    for h in headers:
        html_parts.append(f"<th>{esc(h)}</th>")
    html_parts.append("</tr></thead><tbody>")
    for _, row in show.iterrows():
        html_parts.append("<tr>")
        for col in columns:
            value = row.get(col, "")
            html_parts.append(f"<td>{esc(value)}</td>")
        html_parts.append("</tr>")
    html_parts.append("</tbody></table></div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_policy_board_links() -> None:
    links = mfds_board_home_links()
    html_parts = ["<div class='policy-board-grid'>"]
    for name, url in links.items():
        html_parts.append(f"<a class='board-link-card' href='{esc(url)}' target='_blank'><span>↗</span><b>{esc(name)}</b></a>")
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_table(df: pd.DataFrame, height: int = 500) -> None:
    if df.empty:
        st.info("표시할 기사 데이터가 없습니다.")
        return
    view = df[["published_at", "source", "category", "importance", "title", "keywords", "link"]].copy()
    view = view.rename(columns={"published_at": "발행일시", "source": "언론사", "category": "카테고리", "importance": "중요도", "title": "제목", "keywords": "키워드", "link": "원문"})
    st.dataframe(
        view,
        use_container_width=True,
        height=height,
        column_config={
            "원문": st.column_config.LinkColumn("원문", display_text="원문 열기"),
            "제목": st.column_config.TextColumn("제목", width="large"),
            "키워드": st.column_config.TextColumn("키워드", width="medium"),
            "카테고리": st.column_config.TextColumn("카테고리", width="small"),
            "중요도": st.column_config.TextColumn("중요도", width="small"),
        },
        hide_index=True,
    )


def render_kanban_card(row: pd.Series) -> str:
    keywords = [x.strip() for x in str(row.get("keywords", "")).split(",") if x.strip() and x.strip().lower() not in {"nan", "none"}][:4]
    keyword_html = "".join([f"<span class='tag'>{esc(x)}</span>" for x in keywords])
    category = str(row.get("category", "산업/경영") or "산업/경영")
    color = category_palette().get(category, "#64748b")
    source = esc(row.get("source", ""))
    time_value = esc(row.get("time", ""))
    importance = esc(row.get("importance", "일반"))
    title_html = title_with_link(row.get("title", ""), row.get("link", ""))
    return f"<div class='news-card' style='border-left:5px solid {color};'><div class='news-meta'><span class='source-name'>{source}</span><span>{time_value}</span><span class='tag'>{importance}</span></div>{title_html}<div>{keyword_html}</div></div>"


def render_kanban(df: pd.DataFrame, lanes: List[str] | None = None) -> None:
    if lanes is None:
        lanes = ["식약처/규제", "정책/가이드라인", "GMP/품질", "허가/임상", "해외규제", "회수/처분"]
    html_parts = ["<div class='kanban-wrap'>"]
    for lane in lanes:
        lane_df_all = df[df["category"] == lane]
        lane_df = importance_articles(lane_df_all).head(5)
        html_parts.append("<div class='kanban-lane'>")
        html_parts.append(f"<div class='kanban-head'><b>{esc(lane)}</b><span class='kanban-count'>{len(lane_df_all)}건</span></div>")
        if lane_df.empty:
            html_parts.append("<div style='color:#64748b;font-size:13px;padding:12px;'>해당 카테고리 기사가 없습니다.</div>")
        else:
            for _, row in lane_df.iterrows():
                html_parts.append(render_kanban_card(row))
        html_parts.append("</div>")
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def source_status() -> str:
    try:
        cfg = load_rss_config(CONFIG_PATH)
        enabled = [q for q in cfg.get("queries", []) if q.get("enabled", True)]
        boosted = [q for q in enabled if q.get("collection_group") == "core_media_boost"]
        if boosted:
            return f"등록 검색식 {len(enabled)}개 · 핵심언론 강화 {len(boosted)}개"
        return f"등록 검색식 {len(enabled)}개"
    except Exception:
        return "RSS 설정 확인 필요"


def link_diagnostic_table(df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["제목", "언론사", "link 상태", "link 미리보기"])
    rows = []
    for _, row in df.head(limit).iterrows():
        link = str(row.get("link", "") or "").strip()
        rows.append({
            "제목": str(row.get("title", ""))[:70],
            "언론사": row.get("source", ""),
            "link 상태": "있음" if link else "없음",
            "link 미리보기": link[:120] if link else "",
        })
    return pd.DataFrame(rows)


def render_link_diagnostics(all_data: pd.DataFrame, filtered_data: pd.DataFrame) -> None:
    all_count = len(all_data) if all_data is not None else 0
    filtered_count = len(filtered_data) if filtered_data is not None else 0
    all_link_count = int(all_data["link"].fillna("").astype(str).str.strip().ne("").sum()) if all_count and "link" in all_data.columns else 0
    filtered_link_count = int(filtered_data["link"].fillna("").astype(str).str.strip().ne("").sum()) if filtered_count and "link" in filtered_data.columns else 0
    candidate_cols = [c for c in ["link", "url", "article_url", "google_link", "rss_link", "source_url", "article_link", "origin_link"] if all_data is not None and c in all_data.columns]

    with st.expander("🔧 진단 정보 보기", expanded=False):
        st.markdown(
            f"""
            - 실행 버전: **{APP_VERSION}**
            - 전체 기사: **{all_count:,}건** / link 보유: **{all_link_count:,}건** / link 공란: **{max(all_count - all_link_count, 0):,}건**
            - 현재 조회 결과: **{filtered_count:,}건** / link 보유: **{filtered_link_count:,}건** / link 공란: **{max(filtered_count - filtered_link_count, 0):,}건**
            - 확인된 링크 후보 컬럼: `{', '.join(candidate_cols) if candidate_cols else '없음'}`
            """
        )
        if all_count and all_link_count == 0:
            st.warning("현재 누적 CSV의 link 값이 모두 비어 있습니다. v1.9까지 link 컬럼에 일반 텍스트 정리 로직이 적용되어 URL이 제거된 것이 원인으로 보입니다. v1.10에서 로직은 수정했으므로 RSS 수집을 다시 실행하면 신규/동일 기사 중 link가 복구됩니다.")
        elif filtered_count and filtered_link_count == 0:
            st.warning("전체 데이터에는 link가 있을 수 있으나, 현재 조회 조건의 기사에는 link가 없습니다. 기간/언론사 조건을 넓히거나 RSS 수집을 다시 실행해 보셔야 합니다.")
        else:
            st.success("현재 조회 결과에서 link 값이 확인됩니다.")
        st.markdown("**현재 조회 결과 상위 10건 링크 상태**")
        render_pretty_table(link_diagnostic_table(filtered_data), ["제목", "언론사", "link 상태", "link 미리보기"], max_rows=10)


def render_importance_criteria_popover() -> None:
    if hasattr(st, "popover"):
        with st.popover("ⓘ 중요도 기준", use_container_width=True):
            st.markdown(
                """
                **현재 중요도는 제목·RSS 요약 키워드 기반 선별 보조값입니다.**

                - **높음**: 회수, 폐기, 리콜, 행정처분, 판매중지, 품목취소, 영업정지, 부적합, 위해성, 불순물, 오염 등 직접 조치성·품질위험 키워드 포함
                - **중간**: 식약처/규제, 정책/가이드라인, GMP/품질, 해외규제 또는 FDA·EMA·실태조사·데이터완전성 등 QA/규제 관련 키워드 포함
                - **일반**: 위 조건에 해당하지 않는 제약산업, 경영, 임상, 투자, 시장성 기사
                """
            )
    else:
        with st.expander("ⓘ 중요도 기준"):
            st.markdown("높음/중간/일반 기준은 제목·요약 키워드 기반 자동분류입니다.")


def render_collect_scope_popover() -> None:
    if hasattr(st, "popover"):
        with st.popover("ⓘ 수집범위", use_container_width=True):
            st.markdown(
                """
                - v1.4부터 RSS 수집 단계에 **날짜 기준**을 적용합니다.
                - 선택한 수집기간을 Google News RSS 검색식에 `after:YYYY-MM-DD`, `before:YYYY-MM-DD` 조건으로 붙입니다.
                - 단, Google News RSS는 공식 API가 아니므로 결과 누락 또는 정렬 차이가 있을 수 있습니다.
                - 각 검색식당 최대 수집 건수도 함께 제한합니다.
                """
            )
    else:
        with st.expander("ⓘ 수집범위"):
            st.markdown("v1.4부터 after/before 날짜 검색식을 붙여 날짜 기준으로 수집합니다.")


def render_policy_card(row: pd.Series) -> None:
    source = esc(row.get("source", ""))
    published = esc(row.get("published_at", ""))
    ptype = esc(row.get("policy_type", "정책/가이드라인"))
    title_html = title_with_link(row.get("title", ""), row.get("link", ""))
    html = f"<div class='policy-box wide'><div class='news-meta'><span class='source-name'>{source}</span><span>{published}</span><span class='tag'>{ptype}</span></div>{title_html}</div>"
    st.markdown(html, unsafe_allow_html=True)


# 온라인 접속 보호: Streamlit secrets에 APP_PASSWORD가 있을 때만 동작
require_password_if_configured()

# 데이터 로드
all_df = prepare_display_df(load_or_collect_initial())

header(
    "제약뉴스 RSS 대시보드",
    "Google News RSS 기반 제약·바이오·규제 뉴스 모니터링 / Dashboard · 뉴스목록 · 키워드 인텔리전스 · 규제 레이더 · 규제기관 정책",
)

# 조회조건: 기존 큰 영역을 줄여 상단 얇은 검색바 형태로 구성
if all_df.empty:
    min_date = max_date = date.today()
    default_start = max_date - timedelta(days=6)
else:
    date_series = pd.to_datetime(all_df["date"], errors="coerce").dt.date.dropna()
    min_date = date_series.min() if not date_series.empty else date.today()
    max_date = date_series.max() if not date_series.empty else date.today()
    default_start = max(max_date - timedelta(days=6), min_date)

with st.container(border=True):
    st.markdown("<div class='compact-filter-title'>조회조건</div>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5, c6, c7 = st.columns([1.28, 1.05, 1.05, 0.95, 1.55, 0.95, 0.95])
    with c1:
        selected_range = st.date_input("조회기간", value=(default_start, max_date), min_value=min_date, max_value=max(max_date, date.today()), label_visibility="collapsed")
    with c2:
        category_options = ["전체"] + sorted([x for x in all_df["category"].dropna().unique().tolist() if x])
        selected_categories = st.multiselect("카테고리", category_options, default=["전체"], label_visibility="collapsed")
    with c3:
        source_options = ["전체"] + sorted([x for x in all_df["source"].dropna().unique().tolist() if x])
        selected_sources = st.multiselect("언론사", source_options, default=["전체"], label_visibility="collapsed")
    with c4:
        importance_options = ["전체", "높음", "중간", "일반"]
        selected_importance = st.multiselect("중요도", importance_options, default=["전체"], label_visibility="collapsed")
    with c5:
        search_keyword = st.text_input("검색어", placeholder="제목, 키워드, 언론사 검색", label_visibility="collapsed")
    with c6:
        collect_days = st.selectbox("RSS 수집기간", [1, 3, 7, 14, 30, 90], index=2, format_func=lambda x: f"최근 {x}일", label_visibility="collapsed")
    with c7:
        max_items = st.selectbox("쿼리당 수집", [50, 80, 100], index=2, format_func=lambda x: f"{x}건/식", label_visibility="collapsed")

    b1, b2, b3, b4 = st.columns([1.25, 1.0, 1.0, 3.2])
    with b1:
        collect_clicked = st.button(f"🛰️ RSS 수집", type="primary", use_container_width=True)
    with b2:
        render_importance_criteria_popover()
    with b3:
        render_collect_scope_popover()
    with b4:
        st.caption(f"데이터 상태: {source_status()} · 온라인 안정화 버전 · 원문은 Google News RSS 링크를 통해 열립니다.")

if isinstance(selected_range, tuple) and len(selected_range) == 2:
    start_date, end_date = selected_range
else:
    start_date = end_date = selected_range

if collect_clicked:
    try:
        today = date.today()
        collect_start = today - timedelta(days=int(collect_days) - 1)
        with st.spinner(f"Google News RSS 수집 중입니다. 기준: {collect_start} ~ {today}"):
            updated_df, errors, added_count = collect_and_save(start_date=collect_start, end_date=today, max_items_per_query=int(max_items))
        st.success(f"수집 완료: 신규 {added_count}건 추가 / 전체 {len(updated_df)}건 / 수집기준 {collect_start} ~ {today}")
        if errors:
            with st.expander("수집 오류 상세"):
                for err in errors:
                    st.write(f"- {err}")
        st.rerun()
    except Exception as exc:
        st.error(f"수집 실패: {exc}")

filtered_df = filter_news(all_df, start_date, end_date, selected_categories, selected_sources, search_keyword, selected_importance)
filtered_df = prepare_display_df(filtered_df)

render_link_diagnostics(all_df, filtered_df)

excel_bytes = to_excel_bytes(filtered_df)
issue_groups_cache = group_similar_issues(filtered_df, max_groups=8)

st.download_button(
    "📥 현재 조회 결과 엑셀 다운로드",
    data=excel_bytes,
    file_name=f"pharma_news_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

if filtered_df.empty:
    st.warning("현재 필터 조건에 해당하는 기사가 없습니다. 기간 또는 검색어를 조정하거나 RSS 수집을 실행해 주세요.")

# 화면선택: 왼쪽 라디오 제거, 상단 탭형으로 변경
TAB_LABELS = [
    "📊 1. Dashboard",
    "📰 2. 뉴스목록",
    "🔎 3. 키워드 인텔리전스",
    "🛰️ 4. 규제 레이더",
    "🏛️ 5. 규제기관 정책",
]
tab_dashboard, tab_news, tab_keyword, tab_radar, tab_policy = st.tabs(TAB_LABELS)

with tab_dashboard:
    st.subheader("📊 Dashboard")
    now = pd.Timestamp.now()
    df_dt = filtered_df.copy()
    df_dt["published_at_dt"] = pd.to_datetime(df_dt["published_at"], errors="coerce")
    new_24h = int((df_dt["published_at_dt"] >= (now - pd.Timedelta(hours=24))).sum()) if not df_dt.empty else 0
    high_count = int((filtered_df["importance"] == "높음").sum()) if not filtered_df.empty else 0
    policy_count = len(extract_policy_articles(filtered_df)) if not filtered_df.empty else 0
    keyword_count = len(count_keywords(filtered_df))
    category_count = filtered_df["category"].nunique() if not filtered_df.empty else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        kpi_card("전체 기사", f"{len(filtered_df):,}건", "필터 기준")
    with k2:
        kpi_card("최근 24시간", f"{new_24h:,}건", "신규 기사")
    with k3:
        kpi_card("중요도 높음", f"{high_count:,}건", "회수/처분/품질위험 신호")
    with k4:
        kpi_card("정책/가이드", f"{policy_count:,}건", "규제기관 정책성 기사")
    with k5:
        kpi_card("주요 키워드", f"{keyword_count:,}개", f"카테고리 {category_count}개")

    section_title("중요 이슈 요약", "")
    summary_lines = generate_issue_summary(filtered_df)
    st.markdown("<div class='issue-summary'>" + "".join([f"<div>• {esc(line)}</div>" for line in summary_lines]) + "</div>", unsafe_allow_html=True)

    left, right = st.columns([1.35, 0.9], gap="large")
    with left:
        section_title("주요 뉴스", "", compact=True)
        for _, row in importance_articles(filtered_df).head(7).iterrows():
            article_card(row, show_summary=False)
    with right:
        render_keyword_bar(filtered_df, title="키워드 TOP 10")
        section_title("카테고리 분포", "")
        render_category_pie(filtered_df, title="카테고리 분포")
        render_pretty_table(category_ratio_table(filtered_df), ["카테고리", "기사 수", "비중"], max_rows=10)

    section_title("유사 이슈 묶음", "")
    render_issue_groups(issue_groups_cache)

with tab_news:
    st.subheader("📰 뉴스목록")
    if filtered_df.empty:
        st.info("표시할 뉴스가 없습니다.")
    else:
        total_news = len(filtered_df)
        pg1, pg2, pg3, pg4 = st.columns([1.15, 1.0, 1.0, 3.0])
        with pg1:
            page_size = st.selectbox("페이지당 표시", [25, 50, 100], index=1, format_func=lambda x: f"{x}건", key="news_page_size")
        total_pages = max((total_news + int(page_size) - 1) // int(page_size), 1)
        current_page = int(st.session_state.get("news_current_page", 1))
        if current_page > total_pages:
            current_page = total_pages
        if current_page < 1:
            current_page = 1
        st.session_state["news_current_page"] = current_page
        with pg2:
            if st.button("◀ 이전", use_container_width=True, disabled=current_page <= 1):
                st.session_state["news_current_page"] = max(current_page - 1, 1)
                st.rerun()
        with pg3:
            if st.button("다음 ▶", use_container_width=True, disabled=current_page >= total_pages):
                st.session_state["news_current_page"] = min(current_page + 1, total_pages)
                st.rerun()
        with pg4:
            selected_page = st.number_input("페이지", min_value=1, max_value=total_pages, value=current_page, step=1, label_visibility="collapsed")
            if int(selected_page) != current_page:
                st.session_state["news_current_page"] = int(selected_page)
                st.rerun()

        current_page = int(st.session_state.get("news_current_page", 1))
        start_idx = (current_page - 1) * int(page_size)
        end_idx = min(start_idx + int(page_size), total_news)
        page_df = filtered_df.iloc[start_idx:end_idx]
        st.caption(f"총 {total_news:,}건 · {total_pages:,}페이지 · 현재 {current_page:,}/{total_pages:,}페이지 · 표시 {start_idx + 1:,}~{end_idx:,}건")

        for day, day_df in page_df.groupby("date", sort=False):
            st.markdown(f"#### {day}")
            for _, row in day_df.iterrows():
                timeline_item(row)

with tab_keyword:
    st.subheader("🔎 키워드 인텔리전스")
    c1, c2 = st.columns([1.45, 1], gap="large")
    with c1:
        render_category_trend(filtered_df)
    with c2:
        section_title("카테고리 TOP 7", "")
        ctop = category_top_table(filtered_df, limit=7)
        if ctop.empty:
            st.info("표시할 카테고리 데이터가 없습니다.")
        else:
            render_pretty_table(ctop, ["카테고리", "기사 수", "비중"], max_rows=7)

    c3, c4 = st.columns([1, 1], gap="large")
    with c3:
        section_title("카테고리별 키워드 요약", "")
        cks = category_keyword_summary(filtered_df)
        if cks.empty:
            st.info("표시할 카테고리별 키워드 데이터가 없습니다.")
        else:
            render_pretty_table(cks, ["카테고리", "기사 수", "주요 키워드"])
    with c4:
        section_title("대표 관련 기사", "")
        for _, row in representative_articles(filtered_df, limit=5).iterrows():
            article_card(row, show_summary=False)

with tab_radar:
    st.subheader("🛰️ 규제 레이더")
    default_lanes = ["식약처/규제", "정책/가이드라인", "GMP/품질", "허가/임상", "해외규제", "회수/처분"]
    radar_filter = st.multiselect("레이더 표시 카테고리", default_lanes + ["약가/보험", "산업/경영"], default=default_lanes)
    radar_df = filtered_df[filtered_df["category"].isin(radar_filter)] if radar_filter else filtered_df
    render_kanban(radar_df, lanes=radar_filter)

with tab_policy:
    st.subheader("🏛️ 규제기관 정책")
    policy_df = extract_policy_articles(filtered_df)
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        kpi_card("정책성 기사", f"{len(policy_df):,}건", "필터 기준")
    with p2:
        kpi_card("민원인/지침", f"{int(policy_df['policy_type'].str.contains('안내서|지침|해설서', na=False).sum()) if not policy_df.empty else 0:,}건", "안내서·지침")
    with p3:
        kpi_card("예고/고시", f"{int(policy_df['policy_type'].str.contains('예고|고시|규정', na=False).sum()) if not policy_df.empty else 0:,}건", "제·개정 신호")
    with p4:
        kpi_card("약전/기준", f"{int(policy_df['policy_type'].str.contains('약전|기준', na=False).sum()) if not policy_df.empty else 0:,}건", "KP·기준규격")

    section_title("정책/가이드라인 감지 기사", "")
    if policy_df.empty:
        st.info("현재 조회 조건에서 정책/가이드라인성 기사가 감지되지 않았습니다.")
    else:
        for _, row in policy_df.head(15).iterrows():
            render_policy_card(row)

    st.divider()
    section_title("규제기관 정책/가이드라인 게시판 바로가기", "게시판 자체 연결")
    render_policy_board_links()
