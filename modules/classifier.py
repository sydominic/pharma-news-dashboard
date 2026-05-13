from __future__ import annotations

import re
from typing import Dict, List, Tuple

# v1.35/v29: hybrid rule-first classification.
# v28's pure score-first representative category caused unstable results in hard categories.
# This version uses explicit hard rules for event/policy/clinical/regulatory signals and uses scores only as a secondary tie-breaker.

MFDS_TERMS = [
    "식약처", "식품의약품안전처", "MFDS", "의약품안전나라", "마약류통합관리시스템",
]
OVERSEAS_REGULATORS = [
    "FDA", "USFDA", "미 FDA", "미국 FDA", "미 식품의약국", "미국 식품의약국", "미국식품의약국", "식품의약국",
    "EMA", "유럽의약품청", "유럽 의약품청", "유럽 의약품 관리청", "European Medicines Agency",
    "European Commission", "유럽 집행위", "EU 집행위", "EC", "EudraLex",
    "PIC/S", "PICS", "PICs", "의약품실사상호협력기구",
    "ICH", "국제의약품규제조화위원회",
    "PMDA", "일본 PMDA", "일본 의약품의료기기종합기구",
    "EDQM", "유럽의약품품질위원회", "Ph. Eur", "Ph.Eur",
    "WHO", "세계보건기구", "CHMP", "MHRA", "영국 의약품규제청", "영국 의약품건강관리제품규제청", "Health Canada", "캐나다 보건부", "TGA", "호주 의약품청",
]
DOMESTIC_REGULATORS = MFDS_TERMS + ["보건복지부", "복지부", "심평원", "건강보험심사평가원", "질병관리청"]
REGULATOR_KEYWORDS = DOMESTIC_REGULATORS + OVERSEAS_REGULATORS

POLICY_ACTION_KEYWORDS = [
    "가이드라인", "가이드", "guidance", "guideline", "draft guidance", "final guidance",
    "민원인안내서", "민원인 안내서", "공무원지침서", "공무원 지침서", "안내서", "지침", "해설서", "질의응답", "Q&A",
    "행정예고", "입법예고", "예고", "고시", "훈령", "예규", "규정", "공고", "공식문서", "공식 문서",
    "제정", "개정", "일부개정", "전부개정", "시행", "시행령", "시행규칙", "법령", "약사법",
    "대한민국약전", "약전", "KP", "Ph. Eur", "Ph.Eur", "USP", "기준규격", "기준 규격", "시험법",
    "reflection paper", "concept paper", "consultation", "notice", "notification", "update", "revision", "revised",
]
POLICY_CHANGE_KEYWORDS = [
    "정책변화", "정책 변화", "정책추가", "정책 추가", "제도개선", "제도 개선", "개선방안", "개선 방안",
    "혁신방안", "혁신 방안", "의견수렴", "의견 수렴", "시범사업", "로드맵", "규제혁신", "규제 혁신",
    "허가·심사", "허가 심사", "허가심사", "심사 속도", "신속심사", "규제개선", "규제 개선", "심사기준", "심사 기준",
]
POLICY_GUIDE_KEYWORDS = POLICY_ACTION_KEYWORDS + POLICY_CHANGE_KEYWORDS

RECALL_KEYWORDS = [
    "회수", "회수·폐기", "회수폐기", "폐기", "리콜", "recall", "행정처분", "판매중지", "판매 중지",
    "품목취소", "허가취소", "영업정지", "잠정 중지", "잠정중지", "사용중지", "처분", "수입중지", "수입 중지",
]

# 대표분류/규제레이더의 회수·처분은 반드시 사건형 단어가 있어야 합니다.
# 품질부적합·불순물 같은 위험 단어만으로 회수/처분에 넣으면 레이더가 흔들립니다.
STRICT_RECALL_EVENT_KEYWORDS = [
    "회수", "회수·폐기", "회수폐기", "리콜", "recall", "행정처분", "판매중지", "판매 중지",
    "품목정지", "품목 취소", "품목취소", "업무정지", "영업정지", "허가취소", "허가 취소",
    "사용중지", "사용 중지", "잠정중지", "잠정 중지", "수입중지", "수입 중지",
    "폐기명령", "폐기 명령", "과징금", "고발", "처분",
]
RECALL_RISK_KEYWORDS = [
    "부적합", "위해성", "안전성 서한", "안전성 정보", "검출", "이물", "불순물", "오염", "품질부적합",
    "NDMA", "NDSRI", "니트로사민", "트라마돌", "부작용", "이상사례", "adverse event", "safety communication",
]

APPROVAL_KEYWORDS = [
    "허가", "품목허가", "허가변경", "허가 변경", "허가심사", "허가·심사", "신약 허가", "승인", "승인권고", "심사", "사전상담",
    "IND", "NDA", "BLA", "MAA", "임상", "임상시험", "1상", "2상", "3상", "임상1상", "임상2상", "임상3상",
    "적응증", "투여", "바이오시밀러", "치료제", "후보물질", "파이프라인", "희귀의약품", "패스트트랙", "우선심사", "신속심사",
]

GMP_CORE_KEYWORDS = [
    "GMP", "cGMP", "KGMP", "PIC/S", "PICS", "제조소", "제조업체", "제조시설", "제조 시설", "제조·품질", "제조 품질",
    "제조관리", "품질관리", "실태조사", "실사", "점검", "inspection", "audit", "GMP non-compliance",
]
GMP_RISK_KEYWORDS = [
    "데이터완전성", "데이터 완전성", "data integrity", "무균", "sterile", "sterility", "aseptic", "오염", "교차오염", "불순물", "이물",
    "일탈", "deviation", "CAPA", "OOS", "OOT", "부적합", "품질부적합", "품질 결함", "quality defect",
    "제조기록", "제조 기록", "시험기록", "시험 기록", "시험검사", "밸리데이션", "validation",
    "warning letter", "Warning Letter", "483", "Form 483", "import alert", "recall", "compliance", "보완", "시정", "재발방지",
]

MFDS_REG_ACTION_KEYWORDS = [
    "점검", "실태조사", "감시", "약사법", "품목갱신", "허가·심사", "허가 심사", "민원", "기준", "규정",
    "안전관리", "관리기준", "사전상담", "심사", "제도", "정책", "개선방안", "혁신방안", "공고", "고시", "행정예고",
    "회수", "행정처분", "허가", "품목허가", "수입", "수출", "원료의약품", "완제의약품",
]

OVERSEAS_REG_ACTION_KEYWORDS = [
    "guidance", "guideline", "draft guidance", "final guidance", "warning letter", "Warning Letter", "483", "Form 483",
    "import alert", "inspection", "compliance", "regulation", "regulatory", "EudraLex", "CHMP", "recommend", "GMP non-compliance",
    "승인", "승인권고", "가이드라인", "지침", "개정", "업데이트", "공개", "발표", "규제", "점검", "실사", "심사", "허가", "정책", "규정",
]

REIMBURSEMENT_KEYWORDS = [
    "약가", "급여", "보험", "심평원", "건보", "건강보험", "등재", "상한금액", "수가", "급여기준", "약평위", "보험약가", "선별급여",
]

SUPPLY_API_KEYWORDS = [
    "원료", "원료의약품", "API", "공급망", "공급", "수급", "품절", "부족", "위탁", "수탁", "CMO", "CDMO", "위탁생산", "생산설비", "공장",
]

INDUSTRY_KEYWORDS = [
    "투자", "매출", "영업이익", "계약", "기술수출", "라이선스", "인수", "합병", "MOU", "파트너십", "공장",
    "생산", "CDMO", "위탁생산", "공급", "시장", "상장", "실적", "수출", "R&D", "연구개발", "개발",
    "사업", "공개", "발표", "확대", "성장", "경쟁", "도입", "협약", "선정", "진출", "제약", "바이오", "주가", "IR",
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

# Tie-breaker. GMP/품질, 회수/처분은 품질시스템 관점에서 더 중요한 신호로 우선합니다.
REPRESENTATIVE_PRIORITY = [
    "회수/처분",
    "GMP/품질",
    "정책/가이드라인",
    "식약처/규제",
    "허가/임상",
    "해외규제",
    "약가/보험",
    "산업/경영",
]

CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "회수/처분": RECALL_KEYWORDS + RECALL_RISK_KEYWORDS,
    "정책/가이드라인": POLICY_GUIDE_KEYWORDS + REGULATOR_KEYWORDS,
    "식약처/규제": MFDS_TERMS + MFDS_REG_ACTION_KEYWORDS,
    "GMP/품질": GMP_CORE_KEYWORDS + GMP_RISK_KEYWORDS,
    "허가/임상": APPROVAL_KEYWORDS,
    "해외규제": OVERSEAS_REGULATORS + OVERSEAS_REG_ACTION_KEYWORDS,
    "약가/보험": REIMBURSEMENT_KEYWORDS,
    "산업/경영": INDUSTRY_KEYWORDS + SUPPLY_API_KEYWORDS,
}

IMPORTANT_KEYWORDS = (
    RECALL_KEYWORDS + RECALL_RISK_KEYWORDS + GMP_CORE_KEYWORDS + GMP_RISK_KEYWORDS +
    POLICY_GUIDE_KEYWORDS + REGULATOR_KEYWORDS + OVERSEAS_REG_ACTION_KEYWORDS
)

TREND_KEYWORDS = [
    "식약처", "GMP", "KGMP", "허가", "임상", "회수", "행정처분", "FDA", "EMA", "PMDA", "품질", "데이터완전성",
    "무균", "바이오시밀러", "신약", "기술수출", "CDMO", "약가", "급여", "투자", "공장", "수출",
    "불순물", "오염", "밸리데이션", "PIC/S", "ICH", "R&D", "제약", "바이오", "글로벌", "공급망", "치료제",
    "가이드라인", "안내서", "행정예고", "고시", "약전", "제도개선", "입법예고", "Warning Letter", "Form 483", "수입경보",
]

PHARMA_FALLBACK_WORDS = [
    "제약", "바이오", "의약", "의료제품", "약국", "약사", "병원", "신약", "치료제", "항암", "백신", "면역", "희귀질환",
    "임상", "허가", "품목", "복지부", "식약처", "셀트리온", "삼성바이오", "한올", "대웅", "유한양행", "종근당",
]

CLINICAL_APPROVAL_EXCLUSION_FOR_POLICY = [
    "IND 승인", "1상 IND", "임상 1상", "임상1상", "임상 2상", "임상2상", "임상 3상", "임상3상",
    "품목허가", "허가신청", "허가 신청", "승인 기대", "승인 획득", "시판허가", "적응증 확대",
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


def _match_keywords(text: str, keywords: List[str], limit: int | None = None) -> List[str]:
    hits: List[str] = []
    for kw in keywords:
        if kw and kw not in hits and _keyword_hit(text, kw):
            hits.append(kw)
            if limit and len(hits) >= limit:
                break
    return hits


def _combined_text(title: str = "", summary: str = "", article_text: str = "", source: str = "", rss_query: str = "", article_summary: str = "") -> str:
    return " ".join([
        normalize_text(title),
        normalize_text(summary),
        normalize_text(article_summary),
        normalize_text(article_text),
        normalize_text(source),
        normalize_text(rss_query),
    ]).strip()


def is_recall_disposition_event(title: str, summary: str = "", article_text: str = "", article_summary: str = "") -> bool:
    """회수/처분 대표분류용 hard rule. 위험어 단독이 아니라 명시적 조치·처분 단어가 있어야 합니다."""
    text = _combined_text(title, summary, article_text, article_summary=article_summary)
    return _has_any(text, STRICT_RECALL_EVENT_KEYWORDS)


def is_mfds_policy_article(title: str, summary: str = "", article_text: str = "", article_summary: str = "") -> bool:
    text = _combined_text(title, summary, article_text, article_summary=article_summary)
    return _has_any(text, MFDS_TERMS) and _has_any(text, POLICY_ACTION_KEYWORDS + POLICY_CHANGE_KEYWORDS)


def is_overseas_policy_article(title: str, summary: str = "", article_text: str = "", article_summary: str = "") -> bool:
    text = _combined_text(title, summary, article_text, article_summary=article_summary)
    if not (_has_any(text, OVERSEAS_REGULATORS) and _has_any(text, POLICY_ACTION_KEYWORDS + POLICY_CHANGE_KEYWORDS)):
        return False
    # FDA/EMA words in approval/clinical pipeline articles should not be policy/guideline unless policy terms also appear.
    if _has_any(text, CLINICAL_APPROVAL_EXCLUSION_FOR_POLICY) and not _has_any(text, ["guidance", "guideline", "가이드라인", "지침", "규정", "regulation", "EudraLex", "draft guidance", "개정", "행정예고", "고시"]):
        return False
    return True


def is_policy_article(title: str, summary: str = "", article_text: str = "", article_summary: str = "") -> bool:
    return is_mfds_policy_article(title, summary, article_text, article_summary) or is_overseas_policy_article(title, summary, article_text, article_summary)


def is_clinical_approval_article(title: str, summary: str = "", article_text: str = "", article_summary: str = "") -> bool:
    text = _combined_text(title, summary, article_text, article_summary=article_summary)
    return _has_any(text, APPROVAL_KEYWORDS)


def is_reimbursement_article(title: str, summary: str = "", article_text: str = "", article_summary: str = "") -> bool:
    text = _combined_text(title, summary, article_text, article_summary=article_summary)
    return _has_any(text, REIMBURSEMENT_KEYWORDS)


def is_gmp_quality_risk(title: str, summary: str = "", article_text: str = "") -> bool:
    text = _combined_text(title, summary, article_text)
    # 품질/제조 같은 일반어 단독은 제외하고, 위험·실사·위반·GMP 맥락이 함께 있을 때 인정합니다.
    if _has_any(text, GMP_RISK_KEYWORDS):
        return True
    return _has_any(text, GMP_CORE_KEYWORDS) and _has_any(text, [
        "점검", "실사", "실태조사", "위반", "부적합", "오염", "불순물", "무균", "데이터", "Warning Letter", "483", "import alert", "회수", "품질",
    ])


def is_overseas_regulatory(title: str, summary: str = "", article_text: str = "") -> bool:
    text = _combined_text(title, summary, article_text)
    return _has_any(text, OVERSEAS_REGULATORS) and _has_any(text, OVERSEAS_REG_ACTION_KEYWORDS + POLICY_ACTION_KEYWORDS + GMP_RISK_KEYWORDS + APPROVAL_KEYWORDS)


def is_mfds_regulatory(title: str, summary: str = "", article_text: str = "") -> bool:
    text = _combined_text(title, summary, article_text)
    return _has_any(text, MFDS_TERMS) and _has_any(text, MFDS_REG_ACTION_KEYWORDS + APPROVAL_KEYWORDS + RECALL_KEYWORDS + POLICY_ACTION_KEYWORDS + GMP_RISK_KEYWORDS)


def policy_type(title: str, summary: str = "", article_text: str = "") -> str:
    text = _combined_text(title, summary, article_text)
    if _has_any(text, ["FDA", "USFDA", "미 FDA", "미국 FDA"]) and _has_any(text, ["guidance", "guideline", "draft guidance", "final guidance", "가이드라인", "지침"]):
        return "FDA Guidance"
    if _has_any(text, ["European Commission", "유럽 집행위", "EudraLex", "EC", "EMA", "유럽의약품청"]) and _has_any(text, ["EudraLex", "guideline", "guidance", "가이드라인", "개정", "update", "regulation"]):
        return "EC/EMA Guideline"
    if _has_any(text, ["PIC/S", "PICS", "의약품실사상호협력기구"]):
        return "PIC/S GMP Guide"
    if _has_any(text, ["ICH", "국제의약품규제조화위원회"]):
        return "ICH Guideline"
    if _has_any(text, ["PMDA", "일본 PMDA"]):
        return "PMDA Guideline/Notification"
    if _has_any(text, ["EDQM", "Ph. Eur", "Ph.Eur", "유럽의약품품질위원회"]):
        return "EDQM/Ph. Eur."
    if _has_any(text, ["개선방안", "혁신방안", "제도개선", "의견수렴", "허가·심사", "허가 심사", "허가심사", "신속심사", "규제개선"]):
        return "MFDS 허가심사/제도개선"
    if _has_any(text, ["민원인안내서", "민원인 안내서", "안내서", "해설서", "질의응답", "Q&A"]):
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


def _weighted_hits(title: str, summary: str, article_text: str, source: str, rss_query: str, article_summary: str, keywords: List[str]) -> tuple[int, List[str]]:
    title_text = normalize_text(title)
    summary_text = " ".join([normalize_text(summary), normalize_text(article_summary)])
    body_text = " ".join([normalize_text(article_text), normalize_text(source), normalize_text(rss_query)])
    title_hits = _match_keywords(title_text, keywords)
    summary_hits = _match_keywords(summary_text, keywords)
    body_hits = _match_keywords(body_text, keywords)
    hits: List[str] = []
    for kw in title_hits + summary_hits + body_hits:
        if kw not in hits:
            hits.append(kw)
    score = len(title_hits) * 3 + len(summary_hits) * 2 + len(body_hits)
    return score, hits


def score_categories(title: str, summary: str = "", article_text: str = "", source: str = "", rss_query: str = "", article_summary: str = "") -> Dict[str, int]:
    text = _combined_text(title, summary, article_text, source, rss_query, article_summary)
    scores: Dict[str, int] = {cat: 0 for cat in CATEGORY_ORDER}
    raw_hits: Dict[str, List[str]] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score, hits = _weighted_hits(title, summary, article_text, source, rss_query, article_summary, keywords)
        scores[category] = score
        raw_hits[category] = hits

    # Hard-rule gates. Broad categories are suppressed unless the article context supports them.
    if is_recall_disposition_event(title, summary, article_text, article_summary):
        scores["회수/처분"] += 12
    else:
        scores["회수/처분"] = 0

    if is_policy_article(title, summary, article_text, article_summary):
        scores["정책/가이드라인"] += 10
    else:
        scores["정책/가이드라인"] = 0

    if is_mfds_regulatory(title, summary, article_text):
        scores["식약처/규제"] += 7
    else:
        scores["식약처/규제"] = 0

    if is_gmp_quality_risk(title, summary, article_text):
        scores["GMP/품질"] += 9
    else:
        scores["GMP/품질"] = 0

    if is_overseas_regulatory(title, summary, article_text):
        scores["해외규제"] += 6
    else:
        scores["해외규제"] = 0

    if is_clinical_approval_article(title, summary, article_text, article_summary):
        scores["허가/임상"] += 6
    else:
        scores["허가/임상"] = 0

    if is_reimbursement_article(title, summary, article_text, article_summary):
        scores["약가/보험"] += 7
    else:
        scores["약가/보험"] = 0

    # Industry is fallback: keep it but don't let it overpower stronger QA/regulatory categories.
    if not _has_any(text, INDUSTRY_KEYWORDS + SUPPLY_API_KEYWORDS + PHARMA_FALLBACK_WORDS):
        scores["산업/경영"] = 0
    else:
        scores["산업/경영"] = min(scores.get("산업/경영", 0) + 2, 8)

    # FDA/EMA IND approval류는 정책/가이드라인이 아니라 허가/임상 쪽을 우선합니다.
    if _has_any(text, OVERSEAS_REGULATORS) and _has_any(text, CLINICAL_APPROVAL_EXCLUSION_FOR_POLICY):
        scores["허가/임상"] += 8
        if not _has_any(text, ["guidance", "guideline", "가이드라인", "지침", "정책", "규정", "EudraLex", "draft guidance"]):
            scores["정책/가이드라인"] = 0

    return {cat: max(int(score), 0) for cat, score in scores.items()}


def _category_hits(title: str, summary: str, article_text: str, source: str, rss_query: str, article_summary: str) -> Dict[str, List[str]]:
    return {
        cat: _weighted_hits(title, summary, article_text, source, rss_query, article_summary, kws)[1]
        for cat, kws in CATEGORY_KEYWORDS.items()
    }


def classify_article_details(title: str, summary: str = "", article_text: str = "", source: str = "", rss_query: str = "", article_summary: str = "") -> Dict[str, object]:
    text = _combined_text(title, summary, article_text, source, rss_query, article_summary)
    scores = score_categories(title, summary, article_text, source, rss_query, article_summary)
    hits_by_category = _category_hits(title, summary, article_text, source, rss_query, article_summary)

    # Rule-first tags: these are not decided by raw score alone.
    rule_tags: List[str] = []
    if is_recall_disposition_event(title, summary, article_text, article_summary):
        rule_tags.append("회수/처분")
    if is_policy_article(title, summary, article_text, article_summary):
        rule_tags.append("정책/가이드라인")
    if is_gmp_quality_risk(title, summary, article_text):
        rule_tags.append("GMP/품질")
    if is_mfds_regulatory(title, summary, article_text):
        rule_tags.append("식약처/규제")
    if is_clinical_approval_article(title, summary, article_text, article_summary):
        rule_tags.append("허가/임상")
    if is_overseas_regulatory(title, summary, article_text):
        rule_tags.append("해외규제")
    if is_reimbursement_article(title, summary, article_text, article_summary):
        rule_tags.append("약가/보험")

    # Representative category: hard event/policy rules first, score only as secondary support.
    approval_pipeline = _has_any(text, CLINICAL_APPROVAL_EXCLUSION_FOR_POLICY)
    actual_policy = "정책/가이드라인" in rule_tags
    if "회수/처분" in rule_tags:
        category = "회수/처분"
    elif actual_policy:
        # FDA IND approval류는 policy term이 없으면 정책이 아니지만, actual_policy=True면 지침/고시 등 정책성 용어가 확인된 상태입니다.
        category = "정책/가이드라인"
    elif "GMP/품질" in rule_tags:
        category = "GMP/품질"
    elif "식약처/규제" in rule_tags and not ("허가/임상" in rule_tags and "해외규제" in rule_tags and not "식약처/규제" in rule_tags):
        category = "식약처/규제"
    elif "허가/임상" in rule_tags:
        category = "허가/임상"
    elif "해외규제" in rule_tags:
        category = "해외규제"
    elif "약가/보험" in rule_tags:
        category = "약가/보험"
    elif _has_any(text, INDUSTRY_KEYWORDS + SUPPLY_API_KEYWORDS + PHARMA_FALLBACK_WORDS):
        category = "산업/경영"
        scores[category] = max(scores.get(category, 0), 1)
    else:
        category = "산업/경영"
        scores[category] = max(scores.get(category, 0), 1)

    # Multi-tags: hard-rule tags first, then score-supported broader context.
    tags: List[str] = []
    for cat in rule_tags:
        if cat not in tags:
            tags.append(cat)
    for cat in CATEGORY_ORDER:
        threshold = 6 if cat != "산업/경영" else 7
        if scores.get(cat, 0) >= threshold and cat not in tags:
            tags.append(cat)
    if category not in tags:
        tags.insert(0, category)

    keyword_hits: List[str] = []
    for cat in [category] + [c for c in CATEGORY_ORDER if c != category]:
        for kw in hits_by_category.get(cat, []):
            if kw not in keyword_hits:
                keyword_hits.append(kw)
            if len(keyword_hits) >= 10:
                break
        if len(keyword_hits) >= 10:
            break
    if not keyword_hits:
        keyword_hits = fallback_keywords(text, max_keywords=6)

    high_risk = _has_any(text, [
        "회수", "행정처분", "판매중지", "품목취소", "영업정지", "부적합", "위해성", "불순물", "오염", "리콜", "폐기",
        "Warning Letter", "Form 483", "import alert", "GMP non-compliance", "무균", "데이터완전성", "data integrity",
    ])
    regulatory_signal = category in ["회수/처분", "정책/가이드라인", "식약처/규제", "GMP/품질", "해외규제"] or any(t in ["회수/처분", "정책/가이드라인", "식약처/규제", "GMP/품질", "해외규제"] for t in tags)

    if high_risk:
        importance = "높음"
    elif regulatory_signal:
        importance = "중간"
    else:
        importance = "일반"

    score_text = "; ".join([f"{cat}:{scores.get(cat, 0)}" for cat in CATEGORY_ORDER if scores.get(cat, 0) > 0])
    if not score_text:
        score_text = "산업/경영:1"
    evidence = ", ".join(keyword_hits[:8]) if keyword_hits else "직접 키워드 부족"
    basis_parts = ["제목", "RSS요약"]
    if normalize_text(article_summary):
        basis_parts.append("기사요약")
    if normalize_text(article_text):
        basis_parts.append("본문")
    rule_text = ",".join(rule_tags) if rule_tags else "보조분류"
    classification_reason = f"대표분류={category}; hard_rule={rule_text}; 근거={evidence}; 분석범위={'+'.join(basis_parts)}"

    return {
        "category": category,
        "keywords": ", ".join(keyword_hits[:8]),
        "importance": importance,
        "qa_flag": bool(regulatory_signal or high_risk),
        "sub_tags": ", ".join(tags[:6]),
        "classification_reason": classification_reason,
        "classification_score": score_text,
    }

def classify_article(title: str, summary: str = "", article_text: str = "", source: str = "", rss_query: str = "", article_summary: str = "") -> Tuple[str, str, str, bool]:
    result = classify_article_details(title, summary, article_text, source, rss_query, article_summary)
    return str(result["category"]), str(result["keywords"]), str(result["importance"]), bool(result["qa_flag"])


def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    normalized = normalize_text(text)
    hits: List[str] = []
    for kw in TREND_KEYWORDS:
        if _keyword_hit(normalized, kw) and kw not in hits:
            hits.append(kw)
    return hits[:max_keywords]


def fallback_keywords(text: str, max_keywords: int = 5) -> List[str]:
    normalized = normalize_text(text)
    tokens = re.findall(r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9·\-/]{1,24}", normalized)
    stopwords = {
        "그리고", "대한", "관련", "기반", "발표", "공개", "확대", "추진", "위한", "이번", "통해", "기자", "뉴스",
        "데일리팜", "히트뉴스", "팜뉴스", "약업신문", "약업닷컴", "바이오스펙테이터", "메디파나뉴스", "메디파나", "의학신문", "한국의약통신", "헬스코리아뉴스", "약사공론",
    }
    result: List[str] = []
    for token in tokens:
        t = token.strip("-·/")
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
