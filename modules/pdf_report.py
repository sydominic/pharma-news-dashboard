from __future__ import annotations

from datetime import datetime
from io import BytesIO
import re
from typing import Iterable

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from .policy_links import extract_policy_articles

try:
    pdfmetrics.registerFont(UnicodeCIDFont("HYGothic-Medium"))
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    FONT_BOLD = "HYGothic-Medium"
    FONT_REG = "HYSMyeongJo-Medium"
except Exception:
    FONT_BOLD = "Helvetica-Bold"
    FONT_REG = "Helvetica"

NAVY = colors.HexColor("#081f3f")
NAVY2 = colors.HexColor("#123c68")
BLUE = colors.HexColor("#0065d8")
TEAL = colors.HexColor("#00a6a6")
ORANGE = colors.HexColor("#f47b20")
PURPLE = colors.HexColor("#6f52c9")
RED = colors.HexColor("#d94d4d")
GRAY_TEXT = colors.HexColor("#475569")
LIGHT_LINE = colors.HexColor("#d7e1ee")
LIGHT_BG = colors.HexColor("#f5f8fc")
WHITE = colors.white
BLACKISH = colors.HexColor("#0b213d")

CATEGORY_COLORS = {
    "식약처/규제": BLUE,
    "정책/가이드라인": PURPLE,
    "GMP/품질": TEAL,
    "허가/임상": colors.HexColor("#68b545"),
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
    return re.sub(r"\s+", " ", text)


def _fmt_date(value: object) -> str:
    text = _safe(value)
    return text.replace("-", ".")


def _ellipsis(text: object, max_chars: int) -> str:
    text = _safe(text)
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


def _font_size_to_fit(c: canvas.Canvas, text: str, font: str, start_size: int, max_width: float, min_size: int = 7) -> int:
    size = start_size
    while size > min_size and c.stringWidth(text, font, size) > max_width:
        size -= 1
    return size


def _wrap_text(c: canvas.Canvas, text: object, font: str, size: int, max_width: float, max_lines: int = 2) -> list[str]:
    text = _safe(text)
    if not text:
        return [""]
    words = re.split(r"(\s+)", text)
    lines: list[str] = []
    current = ""
    for token in words:
        trial = current + token
        if c.stringWidth(trial, font, size) <= max_width:
            current = trial
        else:
            if current.strip():
                lines.append(current.strip())
            current = token.strip()
        if len(lines) >= max_lines:
            break
    if len(lines) < max_lines and current.strip():
        lines.append(current.strip())
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if len(lines) == max_lines and c.stringWidth(lines[-1], font, size) > max_width:
        lines[-1] = _ellipsis(lines[-1], 30)
    return lines[:max_lines]


def _draw_rounded_rect(c: canvas.Canvas, x: float, y: float, w: float, h: float, radius: float = 8, fill=WHITE, stroke=LIGHT_LINE, width: float = 0.8) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(width)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)


def _draw_section_header(c: canvas.Canvas, x: float, y: float, w: float, title: str, icon: str = "") -> None:
    c.setFillColor(NAVY)
    c.roundRect(x, y - 8, w, 18, 6, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 10)
    c.drawString(x + 8, y - 2, title)


def _category_counts(df: pd.DataFrame, limit: int = 7) -> pd.DataFrame:
    if df is None or df.empty or "category" not in df.columns:
        return pd.DataFrame(columns=["category", "count", "ratio"])
    counts = df["category"].fillna("기타").replace({"": "기타"}).value_counts().reset_index()
    counts.columns = ["category", "count"]
    total = int(counts["count"].sum()) or 1
    counts["ratio"] = counts["count"].apply(lambda x: x / total)
    return counts.head(limit)


def _importance_articles(df: pd.DataFrame, limit: int = 5) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    order = {"높음": 3, "중간": 2, "일반": 1}
    work = df.copy()
    work["_rank"] = work.get("importance", "일반").map(order).fillna(1) if "importance" in work.columns else 1
    work["_dt"] = pd.to_datetime(work.get("published_at", ""), errors="coerce")
    return work.sort_values(["_rank", "_dt"], ascending=[False, False]).head(limit)


def _issue_summary_lines(df: pd.DataFrame) -> list[str]:
    if df is None or df.empty:
        return ["현재 조회 조건에 해당하는 기사가 없습니다."]
    total = len(df)
    policy = int((df.get("category", pd.Series(dtype=str)) == "정책/가이드라인").sum())
    recall = int((df.get("category", pd.Series(dtype=str)) == "회수/처분").sum())
    gmp = int((df.get("category", pd.Series(dtype=str)) == "GMP/품질").sum())
    overseas = int((df.get("category", pd.Series(dtype=str)) == "해외규제").sum())
    high = int((df.get("importance", pd.Series(dtype=str)) == "높음").sum())
    top = _category_counts(df, limit=1)
    lines = [f"조회기간 내 총 {total:,}건의 기사가 수집·분류되었습니다."]
    if not top.empty:
        lines.append(f"최다 카테고리는 {top.iloc[0]['category']}이며 {int(top.iloc[0]['count'])}건입니다.")
    if policy:
        lines.append(f"정책/가이드라인성 기사 {policy}건이 감지되어 공식 게시판 확인이 권장됩니다.")
    if recall or high:
        lines.append(f"회수/처분 {recall}건 및 중요도 높음 {high}건은 우선 검토 대상입니다.")
    if gmp:
        lines.append(f"GMP/품질 관련 기사 {gmp}건이 감지되었습니다.")
    if overseas:
        lines.append(f"FDA/EMA 등 해외규제 관련 기사 {overseas}건이 감지되었습니다.")
    return lines[:4]


def _draw_kpi(c: canvas.Canvas, x: float, y: float, w: float, h: float, label: str, value: str, color) -> None:
    _draw_rounded_rect(c, x, y, w, h, radius=7, fill=WHITE, stroke=LIGHT_LINE)
    c.setFillColor(color)
    c.circle(x + 18, y + h / 2, 12, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 12)
    c.drawCentredString(x + 18, y + h / 2 - 4, "•")
    c.setFillColor(BLACKISH)
    c.setFont(FONT_BOLD, 9)
    c.drawString(x + 36, y + h - 17, label)
    c.setFont(FONT_BOLD, 20)
    c.drawString(x + 36, y + 12, value)


def _draw_category_bars(c: canvas.Canvas, df: pd.DataFrame, x: float, y: float, w: float, h: float) -> None:
    _draw_section_header(c, x, y + h - 8, w, "카테고리 상위 7", "")
    top = _category_counts(df, limit=7)
    if top.empty:
        c.setFillColor(GRAY_TEXT)
        c.setFont(FONT_REG, 9)
        c.drawString(x + 8, y + h - 36, "표시할 카테고리 데이터가 없습니다.")
        return
    max_count = max(int(top["count"].max()), 1)
    row_y = y + h - 38
    for idx, row in top.iterrows():
        cat = _safe(row["category"])
        count = int(row["count"])
        ratio = float(row["ratio"])
        color = CATEGORY_COLORS.get(cat, BLUE)
        c.setFillColor(BLACKISH)
        c.setFont(FONT_BOLD, 8.2)
        c.drawString(x + 8, row_y, _ellipsis(cat, 10))
        bar_x = x + 72
        bar_w = max(12, (w - 128) * count / max_count)
        c.setFillColor(colors.HexColor("#eaf3ff"))
        c.roundRect(bar_x, row_y - 2, w - 128, 7, 3, fill=1, stroke=0)
        c.setFillColor(color)
        c.roundRect(bar_x, row_y - 2, bar_w, 7, 3, fill=1, stroke=0)
        c.setFillColor(GRAY_TEXT)
        c.setFont(FONT_REG, 7.7)
        c.drawRightString(x + w - 8, row_y - 1, f"{count}건 ({ratio*100:.1f}%)")
        row_y -= 17


def _draw_issue_summary(c: canvas.Canvas, df: pd.DataFrame, x: float, y: float, w: float, h: float) -> None:
    _draw_section_header(c, x, y + h - 8, w, "중요 이슈 요약", "")
    line_y = y + h - 35
    c.setFillColor(BLACKISH)
    for i, line in enumerate(_issue_summary_lines(df), start=1):
        c.setFillColor(BLUE)
        c.circle(x + 12, line_y + 3, 6, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(FONT_BOLD, 7)
        c.drawCentredString(x + 12, line_y, str(i))
        c.setFillColor(BLACKISH)
        c.setFont(FONT_REG, 8.6)
        wrapped = _wrap_text(c, line, FONT_REG, 8.6, w - 32, max_lines=2)
        for j, txt in enumerate(wrapped):
            c.drawString(x + 24, line_y - j * 10, txt)
        line_y -= 22


def _draw_issue_groups(c: canvas.Canvas, groups: list[dict], x: float, y: float, w: float, h: float) -> None:
    _draw_section_header(c, x, y + h - 8, w, "유사 이슈 묶음 상위 3", "")
    if not groups:
        c.setFillColor(GRAY_TEXT)
        c.setFont(FONT_REG, 8.5)
        c.drawString(x + 8, y + h - 35, "유사 이슈로 묶인 기사가 충분하지 않습니다.")
        return
    item_y = y + h - 35
    for idx, group in enumerate(groups[:3], start=1):
        c.setFillColor(CATEGORY_COLORS.get(group.get("category"), BLUE))
        c.circle(x + 11, item_y + 2, 7, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(FONT_BOLD, 7.5)
        c.drawCentredString(x + 11, item_y - 1, str(idx))
        c.setFillColor(BLACKISH)
        c.setFont(FONT_BOLD, 8.5)
        title = _ellipsis(group.get("representative_title", ""), 43)
        c.drawString(x + 25, item_y, title)
        c.setFillColor(GRAY_TEXT)
        c.setFont(FONT_REG, 7.4)
        sources = ", ".join(sorted([_safe(s) for s in group.get("sources", []) if _safe(s)])[:4])
        c.drawString(x + 25, item_y - 10, f"{len(group.get('rows', []))}건 · {group.get('category', '')} · {sources}")
        item_y -= 27


def _draw_articles(c: canvas.Canvas, title: str, df: pd.DataFrame, x: float, y: float, w: float, h: float, limit: int = 5) -> None:
    _draw_section_header(c, x, y + h - 8, w, title, "")
    if df is None or df.empty:
        c.setFillColor(GRAY_TEXT)
        c.setFont(FONT_REG, 8.5)
        c.drawString(x + 8, y + h - 34, "표시할 기사가 없습니다.")
        return
    row_y = y + h - 34
    for _, row in df.head(limit).iterrows():
        cat = _safe(row.get("category", ""))
        source = _safe(row.get("source", ""))
        title_text = _ellipsis(row.get("title", ""), 52)
        date_text = _safe(row.get("date", ""))[5:].replace("-", ".") if _safe(row.get("date", "")) else ""
        c.setFillColor(CATEGORY_COLORS.get(cat, BLUE))
        c.roundRect(x + 8, row_y - 4, 42, 13, 4, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(FONT_BOLD, 6.8)
        c.drawCentredString(x + 29, row_y, _ellipsis(cat, 6))
        c.setFillColor(BLACKISH)
        c.setFont(FONT_BOLD, 8.0)
        c.drawString(x + 56, row_y, title_text)
        c.setFillColor(GRAY_TEXT)
        c.setFont(FONT_REG, 7.2)
        c.drawRightString(x + w - 8, row_y, date_text)
        c.drawString(x + 56, row_y - 9, source)
        c.setStrokeColor(colors.HexColor("#edf3f9"))
        c.line(x + 8, row_y - 15, x + w - 8, row_y - 15)
        row_y -= 24


def build_pdf_report(df: pd.DataFrame, issue_groups: list[dict] | None, start_date, end_date) -> bytes:
    issue_groups = issue_groups or []
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    m = 12 * mm

    # Header
    header_h = 38 * mm
    c.setFillColor(NAVY)
    c.roundRect(m, height - m - header_h, width - 2 * m, header_h, 12, fill=1, stroke=0)
    c.setFillColor(NAVY2)
    c.circle(width - 30 * mm, height - m - 7 * mm, 30 * mm, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 20)
    c.drawString(m + 10 * mm, height - m - 15 * mm, "제약뉴스 주간 모니터링 리포트")
    c.setFont(FONT_REG, 9)
    c.drawString(m + 10 * mm, height - m - 25 * mm, f"기간: {_fmt_date(start_date)} ~ {_fmt_date(end_date)}  |  생성일시: {datetime.now().strftime('%Y.%m.%d %H:%M')}")
    c.setFillColor(colors.Color(1, 1, 1, alpha=0.08))
    c.setFont(FONT_BOLD, 22)
    c.drawRightString(width - m - 8 * mm, height - m - 27 * mm, "HANALL BIOPHARMA")

    y = height - m - header_h - 12 * mm

    # KPIs
    total = len(df) if df is not None else 0
    policy = int((df.get("category", pd.Series(dtype=str)) == "정책/가이드라인").sum()) if df is not None and not df.empty else 0
    recall = int((df.get("category", pd.Series(dtype=str)) == "회수/처분").sum()) if df is not None and not df.empty else 0
    gmp = int((df.get("category", pd.Series(dtype=str)) == "GMP/품질").sum()) if df is not None and not df.empty else 0
    kpi_w = (width - 2 * m - 9 * mm) / 4
    kpi_h = 22 * mm
    for i, (label, value, color) in enumerate([
        ("전체 기사", f"{total:,}건", NAVY),
        ("정책/가이드", f"{policy:,}건", TEAL),
        ("회수/처분", f"{recall:,}건", ORANGE),
        ("GMP/품질", f"{gmp:,}건", PURPLE),
    ]):
        _draw_kpi(c, m + i * (kpi_w + 3 * mm), y, kpi_w, kpi_h, label, value, color)

    # Row 2
    y2 = y - 34 * mm
    col_w = (width - 2 * m - 5 * mm) / 2
    box_h = 58 * mm
    _draw_rounded_rect(c, m, y2, col_w, box_h, fill=WHITE)
    _draw_rounded_rect(c, m + col_w + 5 * mm, y2, col_w, box_h, fill=WHITE)
    _draw_issue_summary(c, df, m, y2, col_w, box_h)
    _draw_category_bars(c, df, m + col_w + 5 * mm, y2, col_w, box_h)

    # Row 3 issue groups
    y3 = y2 - 39 * mm
    group_h = 34 * mm
    _draw_rounded_rect(c, m, y3, width - 2 * m, group_h, fill=WHITE)
    _draw_issue_groups(c, issue_groups, m, y3, width - 2 * m, group_h)

    # Row 4 articles and policies
    y4 = y3 - 67 * mm
    art_h = 61 * mm
    _draw_rounded_rect(c, m, y4, col_w, art_h, fill=WHITE)
    _draw_rounded_rect(c, m + col_w + 5 * mm, y4, col_w, art_h, fill=WHITE)
    _draw_articles(c, "주요 확인 기사", _importance_articles(df, limit=5), m, y4, col_w, art_h, limit=5)
    policy_df = extract_policy_articles(df) if df is not None and not df.empty else pd.DataFrame()
    _draw_articles(c, "정책/가이드라인 기사", policy_df, m + col_w + 5 * mm, y4, col_w, art_h, limit=5)

    # Footer
    c.setFillColor(GRAY_TEXT)
    c.setFont(FONT_REG, 7)
    c.drawString(m, 9 * mm, "본 리포트는 Google News RSS 모니터링 데이터를 기반으로 자동 생성되었습니다. 원문 및 공식 자료는 각 링크에서 확인하십시오.")
    c.drawRightString(width - m, 9 * mm, "1페이지 리포트")

    c.showPage()
    c.save()
    return buffer.getvalue()
