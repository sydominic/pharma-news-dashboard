from __future__ import annotations

from datetime import datetime
from io import BytesIO
import re

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from .policy_links import extract_policy_articles

# Use one Korean font family to avoid mixed font appearance.
try:
    pdfmetrics.registerFont(UnicodeCIDFont("HYGothic-Medium"))
    FONT = "HYGothic-Medium"
    FONT_BOLD = "HYGothic-Medium"
except Exception:
    FONT = "Helvetica"
    FONT_BOLD = "Helvetica-Bold"

NAVY = colors.HexColor("#081f3f")
NAVY2 = colors.HexColor("#123c68")
BLUE = colors.HexColor("#0065d8")
TEAL = colors.HexColor("#00a6a6")
ORANGE = colors.HexColor("#f47b20")
PURPLE = colors.HexColor("#6f52c9")
RED = colors.HexColor("#d94d4d")
GREEN = colors.HexColor("#68b545")
GRAY_TEXT = colors.HexColor("#526579")
LIGHT_LINE = colors.HexColor("#d7e1ee")
LIGHT_BG = colors.HexColor("#f6f9fd")
BAR_BG = colors.HexColor("#eaf3ff")
WHITE = colors.white
BLACKISH = colors.HexColor("#0b213d")

CATEGORY_COLORS = {
    "식약처/규제": BLUE,
    "정책/가이드라인": PURPLE,
    "GMP/품질": TEAL,
    "허가/임상": GREEN,
    "산업/경영": ORANGE,
    "해외규제": colors.HexColor("#7b61ff"),
    "회수/처분": RED,
    "약가/보험": colors.HexColor("#f6a63a"),
    "기타": colors.HexColor("#94a3b8"),
}


def _safe(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "nat", "null"}:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text


def _fmt_date(value: object) -> str:
    text = _safe(value)
    return text.replace("-", ".")


def _fit_text(c: canvas.Canvas, text: object, max_width: float, font: str = FONT, size: float = 8.0) -> str:
    s = _safe(text)
    if not s:
        return ""
    if c.stringWidth(s, font, size) <= max_width:
        return s
    ell = "…"
    lo, hi = 0, len(s)
    while lo < hi:
        mid = (lo + hi) // 2
        if c.stringWidth(s[:mid] + ell, font, size) <= max_width:
            lo = mid + 1
        else:
            hi = mid
    return s[: max(lo - 1, 0)] + ell


def _wrap_lines(c: canvas.Canvas, text: object, max_width: float, size: float = 8.2, max_lines: int = 2) -> list[str]:
    s = _safe(text)
    if not s:
        return []
    tokens = re.split(r"(\s+)", s)
    lines: list[str] = []
    cur = ""
    for tok in tokens:
        trial = cur + tok
        if c.stringWidth(trial.strip(), FONT, size) <= max_width:
            cur = trial
        else:
            if cur.strip():
                lines.append(cur.strip())
            cur = tok.strip()
            if len(lines) >= max_lines:
                break
    if len(lines) < max_lines and cur.strip():
        lines.append(cur.strip())
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if lines:
        lines[-1] = _fit_text(c, lines[-1], max_width, FONT, size)
    return lines[:max_lines]


def _box(c: canvas.Canvas, x: float, y: float, w: float, h: float, radius: float = 6, fill=WHITE, stroke=LIGHT_LINE) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(0.75)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)


def _section_header(c: canvas.Canvas, x: float, y_top: float, w: float, title: str) -> None:
    c.setFillColor(NAVY)
    c.roundRect(x, y_top - 18, w, 18, 5, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 9.2)
    c.drawString(x + 7, y_top - 12.2, title)


def _category_counts(df: pd.DataFrame, limit: int = 7) -> pd.DataFrame:
    if df is None or df.empty or "category" not in df.columns:
        return pd.DataFrame(columns=["category", "count", "ratio"])
    counts = df["category"].fillna("기타").replace({"": "기타"}).value_counts().reset_index()
    counts.columns = ["category", "count"]
    total = int(counts["count"].sum()) or 1
    counts["ratio"] = counts["count"].apply(lambda x: x / total)
    return counts.head(limit)


def _importance_articles(df: pd.DataFrame, limit: int = 3) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    order = {"높음": 3, "중간": 2, "일반": 1}
    work = df.copy()
    work["_rank"] = work.get("importance", "일반").map(order).fillna(1) if "importance" in work.columns else 1
    work["_dt"] = pd.to_datetime(work.get("published_at", ""), errors="coerce")
    return work.sort_values(["_rank", "_dt"], ascending=[False, False]).head(limit)


def _summary_lines(df: pd.DataFrame) -> list[str]:
    if df is None or df.empty:
        return ["현재 조회 조건에 해당하는 기사가 없습니다."]
    total = len(df)
    policy = int((df.get("category", pd.Series(dtype=str)) == "정책/가이드라인").sum())
    recall = int((df.get("category", pd.Series(dtype=str)) == "회수/처분").sum())
    gmp = int((df.get("category", pd.Series(dtype=str)) == "GMP/품질").sum())
    overseas = int((df.get("category", pd.Series(dtype=str)) == "해외규제").sum())
    high = int((df.get("importance", pd.Series(dtype=str)) == "높음").sum())
    top = _category_counts(df, limit=1)
    lines = [f"조회기간 내 총 {total:,}건의 기사가 수집 및 분류되었습니다."]
    if not top.empty:
        lines.append(f"최다 카테고리는 {top.iloc[0]['category']}이며 {int(top.iloc[0]['count'])}건입니다.")
    if policy:
        lines.append(f"정책/가이드라인성 기사 {policy}건이 감지되었습니다.")
    if recall or high:
        lines.append(f"회수/처분 {recall}건 및 중요도 높음 {high}건은 우선 검토 대상입니다.")
    elif gmp:
        lines.append(f"GMP/품질 관련 기사 {gmp}건이 감지되었습니다.")
    if overseas:
        lines.append(f"FDA/EMA 등 해외규제 관련 기사 {overseas}건이 감지되었습니다.")
    return lines[:4]


def _draw_header(c: canvas.Canvas, x: float, y: float, w: float, h: float, start_date, end_date) -> None:
    c.setFillColor(NAVY)
    c.roundRect(x, y, w, h, 10, fill=1, stroke=0)
    # keep decorative elements inside header only
    c.setFillColor(colors.Color(1, 1, 1, alpha=0.045))
    c.circle(x + w - 22 * mm, y + h - 7 * mm, 19 * mm, fill=1, stroke=0)
    c.setFillColor(colors.Color(1, 1, 1, alpha=0.06))
    c.setFont(FONT_BOLD, 18)
    c.drawRightString(x + w - 9 * mm, y + 8 * mm, "HANALL BIOPHARMA")
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 20)
    c.drawString(x + 10 * mm, y + h - 16 * mm, "제약뉴스 주간 모니터링 리포트")
    c.setFont(FONT, 8.3)
    c.drawString(x + 10 * mm, y + 8 * mm, f"기간: {_fmt_date(start_date)} ~ {_fmt_date(end_date)}  |  생성일시: {datetime.now().strftime('%Y.%m.%d %H:%M')}")


def _draw_kpi(c: canvas.Canvas, x: float, y: float, w: float, h: float, label: str, value: str, color) -> None:
    _box(c, x, y, w, h, radius=6)
    c.setFillColor(color)
    c.circle(x + 12, y + h / 2, 7, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 7)
    c.drawCentredString(x + 12, y + h / 2 - 2, "•")
    c.setFillColor(GRAY_TEXT)
    c.setFont(FONT_BOLD, 7.8)
    c.drawString(x + 24, y + h - 12, label)
    c.setFillColor(BLACKISH)
    c.setFont(FONT_BOLD, 15)
    c.drawString(x + 24, y + 8, value)


def _draw_summary(c: canvas.Canvas, df: pd.DataFrame, x: float, y: float, w: float, h: float) -> None:
    _box(c, x, y, w, h)
    _section_header(c, x, y + h, w, "중요 이슈 요약")
    line_y = y + h - 30
    for idx, line in enumerate(_summary_lines(df), start=1):
        c.setFillColor(BLUE)
        c.circle(x + 11, line_y + 2, 5.2, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(FONT_BOLD, 6.2)
        c.drawCentredString(x + 11, line_y - 0.5, str(idx))
        c.setFillColor(BLACKISH)
        c.setFont(FONT, 8.0)
        wrapped = _wrap_lines(c, line, w - 28, 8.0, max_lines=2)
        for j, txt in enumerate(wrapped):
            c.drawString(x + 21, line_y - j * 9, txt)
        line_y -= 20


def _draw_category_bars(c: canvas.Canvas, df: pd.DataFrame, x: float, y: float, w: float, h: float) -> None:
    _box(c, x, y, w, h)
    _section_header(c, x, y + h, w, "카테고리 상위 7")
    top = _category_counts(df, limit=7)
    if top.empty:
        c.setFillColor(GRAY_TEXT)
        c.setFont(FONT, 8)
        c.drawString(x + 8, y + h - 32, "표시할 카테고리 데이터가 없습니다.")
        return
    max_count = max(int(top["count"].max()), 1)
    row_y = y + h - 32
    for _, row in top.iterrows():
        cat = _safe(row["category"])
        count = int(row["count"])
        ratio = float(row["ratio"])
        color = CATEGORY_COLORS.get(cat, BLUE)
        c.setFillColor(BLACKISH)
        c.setFont(FONT_BOLD, 7.4)
        c.drawString(x + 8, row_y, _fit_text(c, cat, 54, FONT_BOLD, 7.4))
        bar_x = x + 60
        bar_max = w - 118
        c.setFillColor(BAR_BG)
        c.roundRect(bar_x, row_y - 1.7, bar_max, 6, 3, fill=1, stroke=0)
        c.setFillColor(color)
        c.roundRect(bar_x, row_y - 1.7, max(5, bar_max * count / max_count), 6, 3, fill=1, stroke=0)
        c.setFillColor(GRAY_TEXT)
        c.setFont(FONT, 7.2)
        c.drawRightString(x + w - 8, row_y - 1, f"{count}건 ({ratio*100:.1f}%)")
        row_y -= 14


def _draw_issue_groups(c: canvas.Canvas, groups: list[dict], x: float, y: float, w: float, h: float) -> None:
    _box(c, x, y, w, h)
    _section_header(c, x, y + h, w, "유사 이슈 묶음 상위 3")
    if not groups:
        c.setFillColor(GRAY_TEXT)
        c.setFont(FONT, 8)
        c.drawString(x + 8, y + h - 32, "유사 이슈로 묶인 기사가 충분하지 않습니다.")
        return
    row_y = y + h - 31
    for idx, group in enumerate(groups[:3], start=1):
        color = CATEGORY_COLORS.get(group.get("category"), BLUE)
        c.setFillColor(color)
        c.circle(x + 11, row_y + 1.8, 5.8, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(FONT_BOLD, 6.5)
        c.drawCentredString(x + 11, row_y - 0.3, str(idx))
        c.setFillColor(BLACKISH)
        c.setFont(FONT_BOLD, 8.0)
        title = _fit_text(c, group.get("representative_title", ""), w - 48, FONT_BOLD, 8.0)
        c.drawString(x + 22, row_y, title)
        c.setFillColor(GRAY_TEXT)
        c.setFont(FONT, 6.8)
        sources = ", ".join(sorted([_safe(s) for s in group.get("sources", []) if _safe(s)])[:3])
        meta = f"{len(group.get('rows', []))}건 / {group.get('category', '')} / {sources}"
        c.drawString(x + 22, row_y - 9, _fit_text(c, meta, w - 30, FONT, 6.8))
        row_y -= 23


def _draw_article_list(c: canvas.Canvas, heading: str, df: pd.DataFrame, x: float, y: float, w: float, h: float, limit: int = 3) -> None:
    _box(c, x, y, w, h)
    _section_header(c, x, y + h, w, heading)
    if df is None or df.empty:
        c.setFillColor(GRAY_TEXT)
        c.setFont(FONT, 8)
        c.drawString(x + 8, y + h - 32, "표시할 기사가 없습니다.")
        return
    row_y = y + h - 31
    for _, row in df.head(limit).iterrows():
        cat = _safe(row.get("category", ""))
        source = _safe(row.get("source", ""))
        date_text = _safe(row.get("date", ""))[5:].replace("-", ".") if _safe(row.get("date", "")) else ""
        color = CATEGORY_COLORS.get(cat, BLUE)
        c.setFillColor(color)
        c.roundRect(x + 8, row_y - 4, 36, 12, 3.5, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(FONT_BOLD, 6.0)
        c.drawCentredString(x + 26, row_y - 0.2, _fit_text(c, cat, 30, FONT_BOLD, 6.0))
        c.setFillColor(BLACKISH)
        c.setFont(FONT_BOLD, 7.4)
        title = _fit_text(c, row.get("title", ""), w - 68, FONT_BOLD, 7.4)
        c.drawString(x + 50, row_y, title)
        c.setFillColor(GRAY_TEXT)
        c.setFont(FONT, 6.6)
        c.drawString(x + 50, row_y - 8.5, _fit_text(c, source, w - 76, FONT, 6.6))
        c.drawRightString(x + w - 8, row_y - 8.5, date_text)
        c.setStrokeColor(colors.HexColor("#edf3f9"))
        c.line(x + 8, row_y - 14, x + w - 8, row_y - 14)
        row_y -= 25


def build_pdf_report(df: pd.DataFrame, issue_groups: list[dict] | None, start_date, end_date) -> bytes:
    issue_groups = issue_groups or []
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    m = 11 * mm
    content_w = width - 2 * m

    # Header
    header_h = 31 * mm
    header_y = height - m - header_h
    _draw_header(c, m, header_y, content_w, header_h, start_date, end_date)

    # KPI row
    total = len(df) if df is not None else 0
    policy = int((df.get("category", pd.Series(dtype=str)) == "정책/가이드라인").sum()) if df is not None and not df.empty else 0
    recall = int((df.get("category", pd.Series(dtype=str)) == "회수/처분").sum()) if df is not None and not df.empty else 0
    gmp = int((df.get("category", pd.Series(dtype=str)) == "GMP/품질").sum()) if df is not None and not df.empty else 0
    kpi_y = header_y - 6 * mm - 17 * mm
    kpi_h = 17 * mm
    gap = 3 * mm
    kpi_w = (content_w - gap * 3) / 4
    for i, (label, value, color) in enumerate([
        ("전체 기사", f"{total:,}건", NAVY),
        ("정책/가이드", f"{policy:,}건", TEAL),
        ("회수/처분", f"{recall:,}건", ORANGE),
        ("GMP/품질", f"{gmp:,}건", PURPLE),
    ]):
        _draw_kpi(c, m + i * (kpi_w + gap), kpi_y, kpi_w, kpi_h, label, value, color)

    col_gap = 5 * mm
    col_w = (content_w - col_gap) / 2

    # Summary + category bars
    row2_h = 52 * mm
    row2_y = kpi_y - 6 * mm - row2_h
    _draw_summary(c, df, m, row2_y, col_w, row2_h)
    _draw_category_bars(c, df, m + col_w + col_gap, row2_y, col_w, row2_h)

    # Similar issues
    group_h = 38 * mm
    group_y = row2_y - 5 * mm - group_h
    _draw_issue_groups(c, issue_groups, m, group_y, content_w, group_h)

    # Article lists
    art_h = 55 * mm
    art_y = group_y - 5 * mm - art_h
    _draw_article_list(c, "주요 확인 기사", _importance_articles(df, limit=3), m, art_y, col_w, art_h, limit=3)
    policy_df = extract_policy_articles(df) if df is not None and not df.empty else pd.DataFrame()
    _draw_article_list(c, "정책/가이드라인 기사", policy_df, m + col_w + col_gap, art_y, col_w, art_h, limit=3)

    # Footer
    c.setFillColor(GRAY_TEXT)
    c.setFont(FONT, 6.3)
    c.drawString(m, 8 * mm, "본 리포트는 Google News RSS 모니터링 데이터를 기반으로 자동 생성되었습니다.")
    c.drawRightString(width - m, 8 * mm, "1Page Report")

    c.showPage()
    c.save()
    return buffer.getvalue()
