from __future__ import annotations

import html
import re
from typing import Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# Conservative, non-AI article enrichment.
# It tries to fetch the publisher/Google News article text, but gracefully falls back to RSS summary.

REGULATORY_SUMMARY_PRIORITY_TERMS = [
    "식약처", "식품의약품안전처", "MFDS", "FDA", "EMA", "PMDA", "EDQM", "PIC/S", "ICH", "MHRA",
    "가이드라인", "지침", "고시", "행정예고", "입법예고", "약전", "규정", "정책", "제도", "허가", "승인", "임상",
    "GMP", "실태조사", "실사", "제조소", "품질", "회수", "행정처분", "판매중지", "부적합", "불순물", "오염", "무균",
    "warning letter", "form 483", "import alert", "guidance", "guideline", "regulation", "inspection", "recall", "data integrity",
]

BOILERPLATE_PATTERNS = [
    r"무단전재\s*및\s*재배포\s*금지",
    r"Copyright\s*\(?.{0,30}\)?\s*All\s*rights\s*reserved\.?",
    r"저작권자.*무단.*금지",
    r"관련기사", r"인기기사", r"많이 본 기사", r"이 기자의 다른기사", r"기사제보", r"구독", r"로그인",
]


def normalize_text(value: object, max_chars: int | None = None) -> str:
    text = "" if value is None else str(value)
    for _ in range(3):
        new_text = html.unescape(text)
        if new_text == text:
            break
        text = new_text
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text.lower() in {"nan", "none", "null", "nat"}:
        text = ""
    if max_chars and len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0]
    return text


def _strip_noise(text: str) -> str:
    cleaned = normalize_text(text)
    for pattern in BOILERPLATE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def clean_article_html(page_html: str, max_chars: int = 6000) -> str:
    soup = BeautifulSoup(page_html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "form", "nav", "footer", "header", "aside"]):
        tag.decompose()

    candidates = []
    for selector in ["article", "main", "#articleBody", ".article_body", ".article-body", ".news_body", ".news-body", ".content", ".view_cont", ".articleView"]:
        try:
            for node in soup.select(selector):
                text = node.get_text(" ", strip=True)
                if text and len(text) > 180:
                    candidates.append(text)
        except Exception:
            pass

    if not candidates:
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        paragraph_text = " ".join([p for p in paragraphs if len(p) >= 20])
        if paragraph_text:
            candidates.append(paragraph_text)

    if not candidates and soup.body:
        candidates.append(soup.body.get_text(" ", strip=True))

    if not candidates:
        return ""

    text = max(candidates, key=len)
    text = _strip_noise(text)
    # Google News/consent/interstitial pages are not useful as article body.
    if any(marker in text[:600].lower() for marker in ["enable javascript", "google news", "뉴스.google", "consent"]):
        return ""
    return normalize_text(text, max_chars=max_chars)


def fetch_article_text(url: str, timeout_sec: int = 5, max_chars: int = 6000) -> Tuple[str, str]:
    url = normalize_text(url)
    if not url or not url.startswith(("http://", "https://")):
        return "", "링크없음"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.6,en;q=0.5",
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout_sec, allow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type and response.text[:20].lstrip().startswith("{"):
            return "", "본문수집제한"
        text = clean_article_html(response.text, max_chars=max_chars)
        if len(text) < 160:
            host = urlparse(getattr(response, "url", url)).netloc
            return "", f"본문짧음:{host}" if host else "본문짧음"
        return text, "본문수집성공"
    except Exception as exc:
        return "", f"본문수집실패:{type(exc).__name__}"


def split_sentences(text: str) -> list[str]:
    clean = normalize_text(text)
    if not clean:
        return []
    parts = re.split(r"(?<=[.!?。])\s+|(?<=[다요임됨니다])\.\s*|\s{2,}", clean)
    sentences: list[str] = []
    for part in parts:
        s = normalize_text(part)
        if len(s) < 12:
            continue
        if len(s) > 260:
            sub = re.split(r"(?<=[다요임됨니다])\s+", s)
            sentences.extend([normalize_text(x) for x in sub if len(normalize_text(x)) >= 12])
        else:
            sentences.append(s)
    return sentences


def sentence_score(sentence: str, title: str = "") -> int:
    score = 0
    s = sentence.lower()
    for term in REGULATORY_SUMMARY_PRIORITY_TERMS:
        if term.lower() in s:
            score += 3
    title_terms = set(re.findall(r"[가-힣A-Za-z0-9]{2,}", title))
    sent_terms = set(re.findall(r"[가-힣A-Za-z0-9]{2,}", sentence))
    score += min(len(title_terms & sent_terms), 5)
    if 35 <= len(sentence) <= 180:
        score += 2
    return score


def summarize_article(title: str, rss_summary: str = "", article_text: str = "", max_lines: int = 4) -> str:
    title = normalize_text(title, max_chars=220)
    rss_summary = normalize_text(rss_summary, max_chars=600)
    article_text = normalize_text(article_text, max_chars=5000)

    base_text = " ".join([rss_summary, article_text]).strip()
    sentences = split_sentences(base_text)
    selected: list[str] = []
    for sentence in sorted(sentences, key=lambda s: sentence_score(s, title), reverse=True):
        sentence = normalize_text(sentence, max_chars=210)
        if not sentence:
            continue
        if any(sentence in prev or prev in sentence for prev in selected):
            continue
        selected.append(sentence)
        if len(selected) >= max_lines:
            break

    # Keep natural order where possible.
    if selected and sentences:
        order = {s: i for i, s in enumerate(sentences)}
        selected = sorted(selected, key=lambda s: order.get(s, 9999))[:max_lines]

    if not selected:
        if rss_summary:
            selected = [rss_summary]
        elif title:
            selected = [title]

    # For very short RSS-only items, add transparent context lines without inventing facts.
    if len(selected) < 3:
        if title and not any(title in s or s in title for s in selected):
            selected.insert(0, title)
        if article_text:
            selected.append("원문 본문 일부를 기준으로 제목·요약보다 넓은 문맥을 반영했습니다.")
        else:
            selected.append("원문 본문 수집이 제한되어 RSS 제목·요약 기준으로 정리했습니다.")

    final: list[str] = []
    for s in selected:
        s = normalize_text(s, max_chars=210).strip("-• ")
        if s and s not in final:
            final.append(s)
        if len(final) >= max(3, min(max_lines, 5)):
            break

    return "\n".join([f"- {line}" for line in final])


def enrich_article(title: str, rss_summary: str, link: str, fetch_body: bool = True, timeout_sec: int = 5, max_chars: int = 6000) -> dict:
    body = ""
    status = "RSS요약사용"
    if fetch_body:
        body, status = fetch_article_text(link, timeout_sec=timeout_sec, max_chars=max_chars)
        if not body:
            status = status or "RSS요약사용"
    summary = summarize_article(title, rss_summary, body, max_lines=4)
    return {
        "article_text": body,
        "article_summary": summary,
        "body_fetch_status": status,
    }
