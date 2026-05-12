from __future__ import annotations

import re
from typing import Dict, List
from urllib.parse import quote

import pandas as pd

from .classifier import is_policy_article, policy_type


def clean_query(text: object, max_terms: int = 4) -> str:
    raw = "" if text is None else str(text)
    raw = re.sub(r"[-–—|·,:;\[\](){}<>\"'“”‘’]", " ", raw)
    tokens = re.findall(r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9+./]{1,24}", raw)
    stop = {
        "데일리팜", "히트뉴스", "팜뉴스", "약업신문", "약업닷컴", "메디파나", "메디파나뉴스", "한국의약통신", "헬스코리아뉴스", "약사공론", "의학신문", "뉴스", "기자", "발표", "공개",
        "관련", "대상", "위한", "통해", "한다", "개최", "추진", "제약", "바이오", "의약품"
    }
    keep: List[str] = []
    priority = ["식약처", "가이드라인", "안내서", "행정예고", "고시", "대한민국약전", "약전", "GMP", "허가", "임상", "품질", "데이터완전성", "무균", "FDA", "EMA", "PMDA", "ICH", "PIC/S"]
    for p in priority:
        if p in raw and p not in keep:
            keep.append(p)
    for token in tokens:
        if token in stop or token in keep:
            continue
        keep.append(token)
        if len(keep) >= max_terms:
            break
    return " ".join(keep[:max_terms]) or raw[:30]


def mfds_board_links(query: str) -> Dict[str, str]:
    q = quote(query)
    return {
        "민원인안내서": f"https://www.mfds.go.kr/brd/m_1060/list.do?srchTp=0&srchWord={q}",
        "제개정고시등": f"https://www.mfds.go.kr/brd/m_207/list.do?srchTp=0&srchWord={q}",
        "입법/행정예고": f"https://www.mfds.go.kr/brd/m_209/list.do?srchTp=0&srchWord={q}",
        "고시훈령예규/고시전문": f"https://www.mfds.go.kr/brd/m_211/list.do?board_id=data0005&srchTp=0&srchWord={q}",
        "식약처 통합검색": f"https://www.mfds.go.kr/search/search.do?searchkey={q}",
    }


def google_official_search_link(query: str) -> str:
    return "https://www.google.com/search?q=" + quote(f"site:mfds.go.kr {query}")


def extract_policy_articles(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    work = df.copy()
    mask = work.apply(lambda r: is_policy_article(r.get("title", ""), r.get("summary", "")) or r.get("category", "") == "정책/가이드라인", axis=1)
    out = work[mask].copy()
    if out.empty:
        return out
    out["policy_type"] = out.apply(lambda r: policy_type(r.get("title", ""), r.get("summary", "")), axis=1)
    out["official_query"] = out.apply(lambda r: clean_query(r.get("title", "")), axis=1)
    out["mfds_search"] = out["official_query"].apply(lambda q: mfds_board_links(q)["식약처 통합검색"])
    out["google_mfds_search"] = out["official_query"].apply(google_official_search_link)
    return out.reset_index(drop=True)


def mfds_board_home_links() -> Dict[str, str]:
    """국내외 규제기관 주요 정책/가이드라인 게시판 바로가기.
    검색어를 붙이지 않은 게시판 자체 링크입니다.
    """
    return {
        "MFDS 법·시행령·시행규칙": "https://www.mfds.go.kr/brd/m_203/list.do",
        "MFDS 고시훈령예규": "https://www.mfds.go.kr/brd/m_211/list.do",
        "MFDS 제개정고시등": "https://www.mfds.go.kr/brd/m_207/list.do",
        "MFDS 입법/행정예고": "https://www.mfds.go.kr/brd/m_209/list.do",
        "MFDS 공무원지침서/민원인안내서": "https://www.mfds.go.kr/brd/m_1060/list.do",
        "MFDS 식의약법령정보": "https://www.mfds.go.kr/law/",
        "MFDS 법률 제·개정 현황": "https://www.mfds.go.kr/brd/m_1087/list.do",
        "FDA Guidance Documents": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents",
        "European Commission EudraLex": "https://health.ec.europa.eu/medicinal-products/eudralex_en#latest-updates",
    }
