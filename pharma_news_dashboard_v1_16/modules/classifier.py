from __future__ import annotations

import re
from typing import Dict, List, Tuple

POLICY_GUIDE_KEYWORDS = [
    "가이드라인", "가이드", "안내서", "민원인안내서", "민원인 안내서", "공무원지침서", "공무원 지침서",
    "지침", "해설서", "질의응답", "Q&A", "qa", "제도개선", "운영방안", "심사지침", "심사 지침",
    "허가심사", "허가·심사", "행정예고", "입법예고", "고시", "훈령", "예규", "제정", "개정", "일부개정",
    "전부개정", "공고", "시행", "시행령", "시행규칙", "규정", "기준", "대한민국약전", "약전", "KP",
    "PIC/S", "ICH", "guidance", "guideline", "draft guidance", "reflection paper", "concept paper"
]

REGULATOR_KEYWORDS = [
    "식약처", "식품의약품안전처", "MFDS", "FDA", "EMA", "PMDA", "PIC/S", "ICH", "WHO", "EDQM", "보건복지부", "복지부"
]

CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "회수/처분": [
        "회수", "폐기", "리콜", "행정처분", "판매중지", "판매 중지", "품목취소", "허가취소", "영업정지",
        "부적합", "위해성", "안전성 서한", "잠정 중지", "잠정중지", "사용중지", "검출", "이물",
        "불순물", "오염", "품질부적합", "처분", "회수·폐기", "회수폐기"
    ],
    "정책/가이드라인": POLICY_GUIDE_KEYWORDS + REGULATOR_KEYWORDS,
    "식약처/규제": [
        "식약처", "MFDS", "식품의약품안전처", "의약품안전나라", "규제", "점검", "실태조사", "감시", "약사법",
        "정책", "제도", "공고", "안내", "품목갱신", "허가·심사", "허가 심사", "심사", "민원", "기준", "규정",
        "정부", "복지부", "보건복지부", "안전관리", "관리기준"
    ],
    "GMP/품질": [
        "GMP", "제조소", "제조업체", "제조·품질", "제조 품질", "품질", "품질관리", "제조관리", "데이터완전성",
        "무균", "밸리데이션", "적격성평가", "오염", "교차오염", "일탈", "CAPA", "품질시스템", "QA", "QC",
        "공정", "제조", "PIC/S", "실사", "공급망", "안정성", "안전사용", "생산", "수입업체"
    ],
    "허가/임상": [
        "허가", "임상", "임상시험", "IND", "NDA", "BLA", "품목허가", "허가변경", "신약", "적응증", "승인",
        "허가심사", "치료제", "바이오시밀러", "3상", "2상", "1상", "후보물질", "투여", "임상투여",
        "파이프라인", "임상 3상", "임상 2상", "임상 1상", "임상3상", "임상2상", "임상1상"
    ],
    "해외규제": [
        "FDA", "EMA", "PMDA", "WHO", "ICH", "PIC/S", "미국", "유럽", "일본", "중국", "EU", "글로벌",
        "해외", "승인권고", "CHMP", "Warning Letter", "워닝레터", "483", "cGMP", "USFDA", "Reuters",
        "European", "GlobalData", "의약품청", "guidance", "guideline"
    ],
    "약가/보험": [
        "약가", "급여", "보험", "심평원", "건보", "건강보험", "등재", "상한금액", "수가", "평가", "급여기준",
        "약평위", "의료보험", "보험약가"
    ],
    "산업/경영": [
        "투자", "매출", "영업이익", "계약", "기술수출", "라이선스", "인수", "합병", "MOU", "파트너십", "공장",
        "생산", "CDMO", "위탁생산", "공급", "시장", "상장", "실적", "수출", "R&D", "연구개발", "파이프라인",
        "제약", "바이오", "제약사", "한올바이오파마", "삼성전자", "셀트리온", "대체조제", "유통", "약국", "개발",
        "사업", "신청", "공개", "발표", "확대", "성장", "경쟁", "도입", "협약", "선정", "진출"
    ],
}

CATEGORY_ORDER = [
    "회수/처분",
    "정책/가이드라인",
    "식약처/규제",
    "GMP/품질",
    "허가/임상",
    "해외규제",
    "약가/보험",
    "산업/경영",
]

IMPORTANT_KEYWORDS = [
    "회수", "폐기", "리콜", "행정처분", "판매중지", "품목취소", "영업정지", "부적합", "위해성",
    "GMP", "실태조사", "데이터완전성", "무균", "오염", "불순물", "식약처", "FDA", "EMA", "Warning Letter", "483",
    "가이드라인", "안내서", "행정예고", "고시", "약전", "제정", "개정"
]

TREND_KEYWORDS = [
    "식약처", "GMP", "허가", "임상", "회수", "행정처분", "FDA", "EMA", "PMDA", "품질", "데이터완전성",
    "무균", "바이오시밀러", "신약", "기술수출", "CDMO", "약가", "급여", "투자", "공장", "수출",
    "불순물", "오염", "밸리데이션", "PIC/S", "ICH", "R&D", "제약", "바이오", "글로벌", "공급망", "치료제",
    "가이드라인", "안내서", "행정예고", "고시", "약전", "제도개선", "입법예고"
]

PHARMA_FALLBACK_WORDS = [
    "제약", "바이오", "의약", "약국", "약사", "병원", "신약", "치료제", "항암", "백신", "면역", "희귀질환",
    "임상", "허가", "품목", "복지부", "식약처", "셀트리온", "삼성바이오", "한올", "대웅", "유한양행", "종근당"
]


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value)
    if text.strip().lower() in {"nan", "none", "nat", "null"}:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _keyword_hit(text: str, keyword: str) -> bool:
    if not keyword:
        return False
    if keyword.isascii():
        return keyword.lower() in text.lower()
    return keyword in text


def is_policy_article(title: str, summary: str = "") -> bool:
    text = f"{normalize_text(title)} {normalize_text(summary)}"
    has_policy = any(_keyword_hit(text, kw) for kw in POLICY_GUIDE_KEYWORDS)
    has_regulator = any(_keyword_hit(text, kw) for kw in REGULATOR_KEYWORDS)
    # 국내 기사에서는 정책 키워드만으로도 정책성 기사로 분류될 수 있게 하되,
    # 일반 기사 오분류를 줄이기 위해 의약/제약 맥락 또는 규제기관 맥락을 같이 본다.
    has_pharma = any(_keyword_hit(text, kw) for kw in PHARMA_FALLBACK_WORDS + ["의약품", "바이오의약품", "의료제품"])
    return has_policy and (has_regulator or has_pharma)


def policy_type(title: str, summary: str = "") -> str:
    text = f"{normalize_text(title)} {normalize_text(summary)}"
    if any(_keyword_hit(text, kw) for kw in ["가이드라인", "가이드", "민원인안내서", "민원인 안내서", "안내서", "해설서", "질의응답", "Q&A", "qa"]):
        return "가이드라인/민원인안내서"
    if any(_keyword_hit(text, kw) for kw in ["공무원지침서", "공무원 지침서", "지침", "심사지침"]):
        return "공무원지침서/지침"
    if any(_keyword_hit(text, kw) for kw in ["행정예고", "입법예고", "예고"]):
        return "입법/행정예고"
    if any(_keyword_hit(text, kw) for kw in ["대한민국약전", "약전", "KP", "시험법", "기준규격"]):
        return "약전/기준규격"
    if any(_keyword_hit(text, kw) for kw in ["고시", "훈령", "예규", "제정", "개정", "일부개정", "전부개정"]):
        return "제·개정 고시/규정"
    if any(_keyword_hit(text, kw) for kw in ["FDA", "EMA", "PMDA", "ICH", "PIC/S", "guidance", "guideline"]):
        return "해외 규제기관 지침"
    return "정책/가이드라인"


def score_categories(title: str, summary: str = "") -> Dict[str, int]:
    text = f"{normalize_text(title)} {normalize_text(summary)}"
    scores: Dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if _keyword_hit(text, kw):
                score += 1
        scores[category] = score
    if is_policy_article(title, summary):
        scores["정책/가이드라인"] = scores.get("정책/가이드라인", 0) + 4
    return scores


def classify_article(title: str, summary: str = "") -> Tuple[str, str, str, bool]:
    text = f"{normalize_text(title)} {normalize_text(summary)}"
    scores = score_categories(title, summary)

    category = "산업/경영"
    max_score = max(scores.values()) if scores else 0
    if max_score > 0:
        best = [cat for cat in CATEGORY_ORDER if scores.get(cat, 0) == max_score]
        category = best[0] if best else "산업/경영"
    elif any(_keyword_hit(text, kw) for kw in PHARMA_FALLBACK_WORDS):
        category = "산업/경영"

    matched = extract_keywords(text, max_keywords=8)
    if not matched:
        matched = fallback_keywords(text, max_keywords=5)

    high_risk = any(_keyword_hit(text, kw) for kw in ["회수", "행정처분", "판매중지", "품목취소", "영업정지", "부적합", "위해성", "불순물", "오염", "리콜", "폐기"])
    regulatory_signal = category in ["회수/처분", "정책/가이드라인", "식약처/규제", "GMP/품질", "해외규제"] or any(_keyword_hit(text, kw) for kw in IMPORTANT_KEYWORDS)

    if high_risk:
        importance = "높음"
    elif regulatory_signal:
        importance = "중간"
    else:
        importance = "일반"

    return category, ", ".join(matched), importance, regulatory_signal


def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    normalized = normalize_text(text)
    hits: List[str] = []
    for kw in TREND_KEYWORDS:
        if _keyword_hit(normalized, kw) and kw not in hits:
            hits.append(kw)
    return hits[:max_keywords]


def fallback_keywords(text: str, max_keywords: int = 5) -> List[str]:
    normalized = normalize_text(text)
    tokens = re.findall(r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9·\-]{1,20}", normalized)
    stopwords = {
        "그리고", "대한", "관련", "기반", "발표", "공개", "확대", "추진", "위한", "이번", "통해", "기자", "뉴스",
        "데일리팜", "히트뉴스", "팜뉴스", "약업신문", "약업닷컴", "바이오스펙테이터", "메디파나뉴스", "메디파나", "의학신문", "한국의약통신", "헬스코리아뉴스", "약사공론"
    }
    result: List[str] = []
    for token in tokens:
        t = token.strip("-·")
        if len(t) < 2 or t in stopwords:
            continue
        if t not in result:
            result.append(t)
        if len(result) >= max_keywords:
            break
    return result


def category_palette() -> Dict[str, str]:
    return {
        "회수/처분": "#d94d4d",
        "정책/가이드라인": "#7b61ff",
        "식약처/규제": "#0065d8",
        "GMP/품질": "#00a6a6",
        "허가/임상": "#68b545",
        "산업/경영": "#f47b20",
        "해외규제": "#8b5cf6",
        "약가/보험": "#f6a63a",
        "기타": "#94a3b8",
    }
