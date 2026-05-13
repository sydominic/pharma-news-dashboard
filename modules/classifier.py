from __future__ import annotations

import re
from typing import Dict, List, Tuple

# v1.32: stricter regulatory classification.
# The purpose is to reduce broad industry/general news from Regulatory Radar and Policy tabs.

MFDS_TERMS = ["식약처", "식품의약품안전처", "MFDS", "의약품안전나라"]
OVERSEAS_REGULATORS = [
    "FDA", "USFDA", "EMA", "European Medicines Agency", "European Commission", "EC", "EudraLex",
    "PIC/S", "PICS", "ICH", "PMDA", "EDQM", "WHO", "CHMP", "MHRA", "Health Canada", "TGA"
]
DOMESTIC_REGULATORS = MFDS_TERMS + ["보건복지부", "복지부", "심평원", "건강보험심사평가원"]
REGULATOR_KEYWORDS = DOMESTIC_REGULATORS + OVERSEAS_REGULATORS

POLICY_ACTION_KEYWORDS = [
    "가이드라인", "가이드", "guidance", "guideline", "draft guidance", "final guidance",
    "민원인안내서", "민원인 안내서", "공무원지침서", "공무원 지침서", "안내서", "지침", "해설서", "질의응답", "Q&A", "qa",
    "행정예고", "입법예고", "예고", "고시", "훈령", "예규", "규정", "공고",
    "제정", "개정", "일부개정", "전부개정", "시행", "시행령", "시행규칙",
    "대한민국약전", "약전", "KP", "Ph. Eur", "Ph.Eur", "USP", "기준규격", "기준 규격", "시험법",
    "EudraLex", "reflection paper", "concept paper", "Q&A", "notice", "notification", "update", "revision", "revised",
]

POLICY_GUIDE_KEYWORDS = POLICY_ACTION_KEYWORDS

RECALL_KEYWORDS = [
    "회수", "회수·폐기", "회수폐기", "폐기", "리콜", "recall", "행정처분", "판매중지", "판매 중지",
    "품목취소", "허가취소", "영업정지", "잠정 중지", "잠정중지", "사용중지", "처분",
]
RECALL_RISK_KEYWORDS = [
    "부적합", "위해성", "안전성 서한", "검출", "이물", "불순물", "오염", "품질부적합", "NDMA", "NDSRI", "트라마돌"
]

APPROVAL_KEYWORDS = [
    "허가", "품목허가", "허가변경", "허가심사", "허가·심사", "신약 허가", "승인", "승인권고", "심사", "사전상담",
    "IND", "NDA", "BLA", "임상", "임상시험", "1상", "2상", "3상", "임상1상", "임상2상", "임상3상",
    "적응증", "투여", "바이오시밀러", "치료제", "후보물질", "파이프라인"
]

GMP_CORE_KEYWORDS = ["GMP", "cGMP", "PIC/S", "PICS", "제조소", "제조업체", "제조·품질", "제조 품질", "실태조사", "실사", "inspection", "audit"]
GMP_RISK_KEYWORDS = [
    "데이터완전성", "data integrity", "무균", "sterile", "aseptic", "오염", "교차오염", "불순물", "이물",
    "일탈", "deviation", "CAPA", "부적합", "품질부적합", "제조기록", "시험기록", "시험검사",
    "warning letter", "Warning Letter", "483", "Form 483", "import alert", "recall", "품질관리", "제조관리", "밸리데이션", "validation",
]

MFDS_REG_ACTION_KEYWORDS = [
    "점검", "실태조사", "감시", "약사법", "품목갱신", "허가·심사", "허가 심사", "민원", "기준", "규정",
    "안전관리", "관리기준", "사전상담", "심사", "제도", "정책", "개선방안", "혁신방안", "공고"
]

OVERSEAS_REG_ACTION_KEYWORDS = [
    "guidance", "guideline", "draft guidance", "final guidance", "warning letter", "Warning Letter", "483", "Form 483",
    "import alert", "inspection", "compliance", "regulation", "regulatory", "EudraLex", "CHMP", "recommend", "approval",
    "승인", "승인권고", "가이드라인", "지침", "개정", "업데이트", "공개", "발표", "규제", "점검", "실사"
]

REIMBURSEMENT_KEYWORDS = [
    "약가", "급여", "보험", "심평원", "건보", "건강보험", "등재", "상한금액", "수가", "급여기준", "약평위", "보험약가"
]

INDUSTRY_KEYWORDS = [
    "투자", "매출", "영업이익", "계약", "기술수출", "라이선스", "인수", "합병", "MOU", "파트너십", "공장",
    "생산", "CDMO", "위탁생산", "공급", "시장", "상장", "실적", "수출", "R&D", "연구개발", "개발",
    "사업", "공개", "발표", "확대", "성장", "경쟁", "도입", "협약", "선정", "진출", "제약", "바이오",
]

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

CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "회수/처분": RECALL_KEYWORDS + RECALL_RISK_KEYWORDS,
    "정책/가이드라인": POLICY_ACTION_KEYWORDS + REGULATOR_KEYWORDS,
    "식약처/규제": MFDS_TERMS + MFDS_REG_ACTION_KEYWORDS,
    "GMP/품질": GMP_CORE_KEYWORDS + GMP_RISK_KEYWORDS,
    "허가/임상": APPROVAL_KEYWORDS,
    "해외규제": OVERSEAS_REGULATORS + OVERSEAS_REG_ACTION_KEYWORDS,
    "약가/보험": REIMBURSEMENT_KEYWORDS,
    "산업/경영": INDUSTRY_KEYWORDS,
}

IMPORTANT_KEYWORDS = (
    RECALL_KEYWORDS + RECALL_RISK_KEYWORDS + GMP_CORE_KEYWORDS + GMP_RISK_KEYWORDS +
    POLICY_ACTION_KEYWORDS + REGULATOR_KEYWORDS
)

TREND_KEYWORDS = [
    "식약처", "GMP", "허가", "임상", "회수", "행정처분", "FDA", "EMA", "PMDA", "품질", "데이터완전성",
    "무균", "바이오시밀러", "신약", "기술수출", "CDMO", "약가", "급여", "투자", "공장", "수출",
    "불순물", "오염", "밸리데이션", "PIC/S", "ICH", "R&D", "제약", "바이오", "글로벌", "공급망", "치료제",
    "가이드라인", "안내서", "행정예고", "고시", "약전", "제도개선", "입법예고"
]

PHARMA_FALLBACK_WORDS = [
    "제약", "바이오", "의약", "의료제품", "약국", "약사", "병원", "신약", "치료제", "항암", "백신", "면역", "희귀질환",
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


def _has_any(text: str, keywords: List[str]) -> bool:
    return any(_keyword_hit(text, kw) for kw in keywords)


def is_mfds_policy_article(title: str, summary: str = "") -> bool:
    text = f"{normalize_text(title)} {normalize_text(summary)}"
    return _has_any(text, MFDS_TERMS) and _has_any(text, POLICY_ACTION_KEYWORDS)


def is_overseas_policy_article(title: str, summary: str = "") -> bool:
    text = f"{normalize_text(title)} {normalize_text(summary)}"
    return _has_any(text, OVERSEAS_REGULATORS) and _has_any(text, POLICY_ACTION_KEYWORDS + OVERSEAS_REG_ACTION_KEYWORDS)


def is_policy_article(title: str, summary: str = "") -> bool:
    # v1.32 stricter rule: regulator/official body + policy/guidance action must coexist.
    return is_mfds_policy_article(title, summary) or is_overseas_policy_article(title, summary)


def is_gmp_quality_risk(title: str, summary: str = "") -> bool:
    text = f"{normalize_text(title)} {normalize_text(summary)}"
    # Do not classify as GMP/quality only because generic words like 품질/제조 appear.
    return _has_any(text, GMP_RISK_KEYWORDS) or (_has_any(text, GMP_CORE_KEYWORDS) and _has_any(text, ["점검", "실사", "위반", "부적합", "오염", "불순물", "Warning Letter", "483", "import alert"]))


def is_overseas_regulatory(title: str, summary: str = "") -> bool:
    text = f"{normalize_text(title)} {normalize_text(summary)}"
    return _has_any(text, OVERSEAS_REGULATORS) and _has_any(text, OVERSEAS_REG_ACTION_KEYWORDS + POLICY_ACTION_KEYWORDS)


def is_mfds_regulatory(title: str, summary: str = "") -> bool:
    text = f"{normalize_text(title)} {normalize_text(summary)}"
    return _has_any(text, MFDS_TERMS) and _has_any(text, MFDS_REG_ACTION_KEYWORDS + APPROVAL_KEYWORDS + RECALL_KEYWORDS + POLICY_ACTION_KEYWORDS)


def policy_type(title: str, summary: str = "") -> str:
    text = f"{normalize_text(title)} {normalize_text(summary)}"
    if _has_any(text, ["FDA", "USFDA"]) and _has_any(text, ["guidance", "guideline", "draft guidance", "final guidance", "가이드라인"]):
        return "FDA Guidance"
    if _has_any(text, ["European Commission", "EudraLex", "EC", "EMA"]) and _has_any(text, ["EudraLex", "guideline", "guidance", "가이드라인", "개정", "update"]):
        return "EC/EMA Guideline"
    if _has_any(text, ["PIC/S", "PICS"]):
        return "PIC/S GMP Guide"
    if _has_any(text, ["ICH"]):
        return "ICH Guideline"
    if _has_any(text, ["PMDA"]):
        return "PMDA Guideline/Notification"
    if _has_any(text, ["EDQM", "Ph. Eur", "Ph.Eur"]):
        return "EDQM/Ph. Eur."
    if _has_any(text, ["민원인안내서", "민원인 안내서", "안내서", "해설서", "질의응답", "Q&A", "qa"]):
        return "MFDS 민원인안내서/해설서"
    if _has_any(text, ["공무원지침서", "공무원 지침서", "지침", "심사지침"]):
        return "MFDS 공무원지침서/지침"
    if _has_any(text, ["행정예고", "입법예고", "예고"]):
        return "MFDS 입법/행정예고"
    if _has_any(text, ["대한민국약전", "약전", "KP", "시험법", "기준규격", "기준 규격"]):
        return "MFDS 약전/기준규격"
    if _has_any(text, ["고시", "훈령", "예규", "제정", "개정", "일부개정", "전부개정"]):
        return "MFDS 제·개정 고시/규정"
    return "공식 정책/가이드라인"


def score_categories(title: str, summary: str = "") -> Dict[str, int]:
    text = f"{normalize_text(title)} {normalize_text(summary)}"
    scores: Dict[str, int] = {cat: 0 for cat in CATEGORY_ORDER}
    for category, keywords in CATEGORY_KEYWORDS.items():
        scores[category] = sum(1 for kw in keywords if _keyword_hit(text, kw))

    # Strict boosts/gates
    if _has_any(text, RECALL_KEYWORDS) or (_has_any(text, RECALL_RISK_KEYWORDS) and _has_any(text, ["회수", "처분", "판매중지", "식약처", "FDA", "부적합"])):
        scores["회수/처분"] += 8
    if is_policy_article(title, summary):
        scores["정책/가이드라인"] += 10
    else:
        # prevent generic policy words from dominating
        scores["정책/가이드라인"] = 0
    if is_mfds_regulatory(title, summary):
        scores["식약처/규제"] += 5
    else:
        scores["식약처/규제"] = 0
    if is_gmp_quality_risk(title, summary):
        scores["GMP/품질"] += 7
    else:
        scores["GMP/품질"] = 0
    if is_overseas_regulatory(title, summary):
        scores["해외규제"] += 6
    else:
        scores["해외규제"] = 0
    if _has_any(text, APPROVAL_KEYWORDS):
        scores["허가/임상"] += 4
    if _has_any(text, REIMBURSEMENT_KEYWORDS):
        scores["약가/보험"] += 4
    return scores


def classify_article(title: str, summary: str = "") -> Tuple[str, str, str, bool]:
    text = f"{normalize_text(title)} {normalize_text(summary)}"
    scores = score_categories(title, summary)

    category = "산업/경영"
    max_score = max(scores.values()) if scores else 0
    if max_score > 0:
        best = [cat for cat in CATEGORY_ORDER if scores.get(cat, 0) == max_score]
        category = best[0] if best else "산업/경영"
    elif _has_any(text, PHARMA_FALLBACK_WORDS):
        category = "산업/경영"

    matched = extract_keywords(text, max_keywords=8)
    if not matched:
        matched = fallback_keywords(text, max_keywords=5)

    high_risk = _has_any(text, ["회수", "행정처분", "판매중지", "품목취소", "영업정지", "부적합", "위해성", "불순물", "오염", "리콜", "폐기"])
    regulatory_signal = category in ["회수/처분", "정책/가이드라인", "식약처/규제", "GMP/품질", "해외규제"]

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
