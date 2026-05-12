from __future__ import annotations

from datetime import datetime
from io import BytesIO
import re

import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .policy_links import extract_policy_articles

# ---------- fonts ----------
_FONT_REG_PATHS = [
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]
_FONT_BOLD_PATHS = [
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/unfonts-core/UnDotumBold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]


def _load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


# ---------- palette ----------
NAVY = "#0b2e5a"
NAVY_SOFT = "#173f73"
BG = "#f4f7fb"
CARD = "#ffffff"
LINE = "#d9e2ee"
TEXT = "#0f2742"
TEXT_SUB = "#60758a"
WHITE = "#ffffff"
BLUE = "#1b6fd8"
TEAL = "#11a5a5"
ORANGE = "#f28b26"
PURPLE = "#6f52c9"
RED = "#d95858"
GREEN = "#67b94f"
LIGHT_BAR = "#e9eff7"

CATEGORY_COLORS = {
    "식약처/규제": BLUE,
    "정책/가이드라인": PURPLE,
    "GMP/품질": TEAL,
    "허가/임상": GREEN,
    "산업/경영": ORANGE,
    "해외규제": "#7b61ff",
    "회수/처분": RED,
    "약가/보험": "#f5ad42",
    "기타": "#94a3b8",
}


# ---------- helpers ----------
def _safe(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "nat", "null"}:
        return ""
    return re.sub(r"\s+", " ", text)


def _fmt_date(value: object) -> str:
    return _safe(value).replace("-", ".")


def _text_size(font, text: str) -> tuple[int, int]:
    if hasattr(font, "getbbox"):
        box = font.getbbox(text)
        return box[2] - box[0], box[3] - box[1]
    return font.getsize(text)


def _fit_text(text: object, font, max_width: int) -> str:
    s = _safe(text)
    if not s:
        return ""
    if _text_size(font, s)[0] <= max_width:
        return s
    ell = "…"
    lo, hi = 0, len(s)
    while lo < hi:
        mid = (lo + hi) // 2
        trial = s[:mid] + ell
        if _text_size(font, trial)[0] <= max_width:
            lo = mid + 1
        else:
            hi = mid
    return s[: max(lo - 1, 0)] + ell


def _wrap_text(text: object, font, max_width: int, max_lines: int) -> list[str]:
    s = _safe(text)
    if not s:
        return []
    words = re.split(r"(\s+)", s)
    lines: list[str] = []
    current = ""
    for token in words:
        trial = (current + token).strip()
        if not trial:
            continue
        if _text_size(font, trial)[0] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
                if len(lines) >= max_lines:
                    break
            current = token.strip()
    if len(lines) < max_lines and current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if lines:
        lines[-1] = _fit_text(lines[-1], font, max_width)
    return lines[:max_lines]


def _rounded(draw: ImageDraw.ImageDraw, box, radius=16, fill=CARD, outline=LINE, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _section_header(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, title: str, font_bold):
    draw.rounded_rectangle((x, y, x + w, y + 34), radius=12, fill=NAVY)
    draw.text((x + 14, y + 8), title, font=font_bold, fill=WHITE)


def _category_counts(df: pd.DataFrame, limit: int = 7) -> pd.DataFrame:
    if df is None or df.empty or "category" not in df.columns:
        return pd.DataFrame(columns=["category", "count", "ratio"])
    counts = df["category"].fillna("기타").replace({"": "기타"}).value_counts().reset_index()
    counts.columns = ["category", "count"]
    total = int(counts["count"].sum()) or 1
    counts["ratio"] = counts["count"] / total
    return counts.head(limit)


def _importance_articles(df: pd.DataFrame, limit: int = 3) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    order = {"높음": 3, "중간": 2, "일반": 1}
    work = df.copy()
    if "importance" in work.columns:
        work["_rank"] = work["importance"].map(order).fillna(1)
    else:
        work["_rank"] = 1
    work["_dt"] = pd.to_datetime(work.get("published_at", ""), errors="coerce")
    return work.sort_values(["_rank", "_dt"], ascending=[False, False]).head(limit)


def _priority_articles(df: pd.DataFrame, limit: int = 3) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    work = df.copy()
    cat_weight = {
        "회수/처분": 5,
        "정책/가이드라인": 4,
        "GMP/품질": 3,
        "해외규제": 2,
    }
    imp_weight = {"높음": 3, "중간": 2, "일반": 1}
    work["_cat_rank"] = work.get("category", pd.Series(dtype=str)).map(cat_weight).fillna(0)
    work["_imp_rank"] = work.get("importance", pd.Series(dtype=str)).map(imp_weight).fillna(1)
    work["_dt"] = pd.to_datetime(work.get("published_at", ""), errors="coerce")
    return work.sort_values(["_cat_rank", "_imp_rank", "_dt"], ascending=[False, False, False]).head(limit)


def _category_concentration_text(df: pd.DataFrame) -> str:
    top = _category_counts(df, limit=1)
    if top.empty:
        return "카테고리 집중도 정보가 없습니다."
    cat = _safe(top.iloc[0]["category"])
    ratio = float(top.iloc[0]["ratio"]) * 100
    return f"카테고리 집중도: {cat} 비중이 {ratio:.1f}%로 가장 높습니다."


def _summary_lines(df: pd.DataFrame) -> list[str]:
    if df is None or df.empty:
        return ["현재 조회 조건에 해당하는 기사가 없습니다."]
    total = len(df)
    cats = df.get("category", pd.Series(dtype=str))
    imp = df.get("importance", pd.Series(dtype=str))
    policy = int((cats == "정책/가이드라인").sum())
    recall = int((cats == "회수/처분").sum())
    gmp = int((cats == "GMP/품질").sum())
    overseas = int((cats == "해외규제").sum())
    high = int((imp == "높음").sum())
    top = _category_counts(df, limit=1)
    lines = [f"조회기간 내 총 {total:,}건의 기사가 수집 및 분류되었습니다."]
    if not top.empty:
        lines.append(f"최다 카테고리는 {top.iloc[0]['category']}이며 {int(top.iloc[0]['count'])}건입니다.")
        lines.append(_category_concentration_text(df))
    if policy and len(lines) < 4:
        lines.append(f"정책/가이드라인성 기사 {policy}건이 감지되어 공식 게시판 확인이 권장됩니다.")
    if (recall or high) and len(lines) < 4:
        lines.append(f"회수/처분 {recall}건 및 중요도 높음 {high}건은 우선 검토 대상입니다.")
    elif gmp and len(lines) < 4:
        lines.append(f"GMP/품질 관련 기사 {gmp}건이 감지되었습니다.")
    if overseas and len(lines) < 4:
        lines.append(f"FDA/EMA 등 해외규제 관련 기사 {overseas}건이 감지되었습니다.")
    return lines[:4]


def build_report_png(df: pd.DataFrame, issue_groups: list[dict] | None, start_date, end_date) -> bytes:
    """Create a fixed-layout A4 report image (PNG)."""
    issue_groups = issue_groups or []

    # A4 portrait at 150 dpi
    W, H = 1240, 1754
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Fonts
    f_title = _load_font(_FONT_BOLD_PATHS, 34)
    f_sub = _load_font(_FONT_REG_PATHS, 16)
    f_section = _load_font(_FONT_BOLD_PATHS, 19)
    f_kpi_label = _load_font(_FONT_BOLD_PATHS, 14)
    f_kpi_value = _load_font(_FONT_BOLD_PATHS, 26)
    f_body = _load_font(_FONT_REG_PATHS, 15)
    f_small = _load_font(_FONT_REG_PATHS, 12)
    f_bold = _load_font(_FONT_BOLD_PATHS, 15)
    f_tag = _load_font(_FONT_BOLD_PATHS, 11)

    margin = 48
    content_w = W - margin * 2

    # Header
    header_h = 180
    _rounded(draw, (margin, margin, margin + content_w, margin + header_h), radius=28, fill=NAVY, outline=NAVY)
    draw.ellipse((W - 360, 0, W - 20, 340), fill=NAVY_SOFT)
    draw.text((margin + 32, margin + 36), "제약뉴스 주간 모니터링 리포트", font=f_title, fill=WHITE)
    meta = f"기간: {_fmt_date(start_date)} ~ {_fmt_date(end_date)}  |  생성일시: {datetime.now().strftime('%Y.%m.%d %H:%M')}"
    draw.text((margin + 32, margin + 110), meta, font=f_sub, fill=WHITE)
    draw.text((W - 410, margin + 114), "HANALL BIOPHARMA", font=_load_font(_FONT_BOLD_PATHS, 22), fill="#2f4f7d")

    # KPI
    total = len(df) if df is not None else 0
    cats = df.get("category", pd.Series(dtype=str)) if df is not None and not df.empty else pd.Series(dtype=str)
    policy = int((cats == "정책/가이드라인").sum())
    recall = int((cats == "회수/처분").sum())
    gmp = int((cats == "GMP/품질").sum())
    kpi_y = margin + header_h + 24
    gap = 16
    kpi_w = (content_w - gap * 3) // 4
    kpi_h = 84
    kpis = [
        ("전체 기사", f"{total:,}건", NAVY),
        ("정책/가이드", f"{policy:,}건", TEAL),
        ("회수/처분", f"{recall:,}건", ORANGE),
        ("GMP/품질", f"{gmp:,}건", PURPLE),
    ]
    for i, (label, value, color) in enumerate(kpis):
        x = margin + i * (kpi_w + gap)
        _rounded(draw, (x, kpi_y, x + kpi_w, kpi_y + kpi_h), radius=18)
        draw.ellipse((x + 16, kpi_y + 26, x + 36, kpi_y + 46), fill=color)
        draw.text((x + 48, kpi_y + 16), label, font=f_kpi_label, fill=TEXT_SUB)
        draw.text((x + 48, kpi_y + 40), value, font=f_kpi_value, fill=TEXT)

    # Summary and categories
    row2_y = kpi_y + kpi_h + 24
    col_gap = 18
    col_w = (content_w - col_gap) // 2
    summary_h = 270
    # Summary
    _rounded(draw, (margin, row2_y, margin + col_w, row2_y + summary_h), radius=18)
    _section_header(draw, margin, row2_y, col_w, "중요 이슈 요약", f_section)
    lines = _summary_lines(df)
    line_y = row2_y + 58
    for idx, line in enumerate(lines[:4], start=1):
        draw.ellipse((margin + 16, line_y + 2, margin + 40, line_y + 26), fill=BLUE)
        num_w, _ = _text_size(f_small, str(idx))
        draw.text((margin + 28 - num_w / 2, line_y + 6), str(idx), font=f_small, fill=WHITE)
        wrapped = _wrap_text(line, f_body, col_w - 72, 2)
        for j, txt in enumerate(wrapped):
            draw.text((margin + 54, line_y + j * 18), txt, font=f_body, fill=TEXT)
        line_y += 46

    # Categories
    cx = margin + col_w + col_gap
    _rounded(draw, (cx, row2_y, cx + col_w, row2_y + summary_h), radius=18)
    _section_header(draw, cx, row2_y, col_w, "카테고리 상위 7", f_section)
    top = _category_counts(df, limit=7)
    bar_y = row2_y + 60
    max_count = int(top["count"].max()) if not top.empty else 1
    for _, row in top.iterrows():
        cat = _safe(row["category"])
        count = int(row["count"])
        ratio = float(row["ratio"])
        color = CATEGORY_COLORS.get(cat, BLUE)
        draw.text((cx + 14, bar_y - 2), _fit_text(cat, f_body, 130), font=f_body, fill=TEXT)
        bx = cx + 140
        bw = col_w - 210
        draw.rounded_rectangle((bx, bar_y + 2, bx + bw, bar_y + 14), radius=6, fill=LIGHT_BAR)
        draw.rounded_rectangle((bx, bar_y + 2, bx + max(18, int(bw * count / max_count)), bar_y + 14), radius=6, fill=color)
        draw.text((cx + col_w - 14 - _text_size(f_small, f"{count}건 ({ratio*100:.1f}%)")[0], bar_y - 1), f"{count}건 ({ratio*100:.1f}%)", font=f_small, fill=TEXT_SUB)
        bar_y += 28

    # Similar issue groups
    group_y = row2_y + summary_h + 22
    group_h = 220
    _rounded(draw, (margin, group_y, margin + content_w, group_y + group_h), radius=18)
    _section_header(draw, margin, group_y, content_w, "유사 이슈 묶음 상위 3", f_section)
    gy = group_y + 60
    if not issue_groups:
        draw.text((margin + 18, gy), "유사 이슈로 묶인 기사가 충분하지 않습니다.", font=f_body, fill=TEXT_SUB)
    else:
        for idx, group in enumerate(issue_groups[:3], start=1):
            color = CATEGORY_COLORS.get(group.get("category", "기타"), BLUE)
            draw.ellipse((margin + 16, gy, margin + 40, gy + 24), fill=color)
            n_w, _ = _text_size(f_small, str(idx))
            draw.text((margin + 28 - n_w / 2, gy + 4), str(idx), font=f_small, fill=WHITE)
            title = _fit_text(group.get("representative_title", ""), f_bold, content_w - 100)
            draw.text((margin + 54, gy - 1), title, font=f_bold, fill=TEXT)
            sources = ", ".join(sorted([_safe(s) for s in group.get("sources", []) if _safe(s)])[:4])
            meta = f"{len(group.get('rows', []))}건 · {group.get('category', '')} · {sources}"
            draw.text((margin + 54, gy + 18), _fit_text(meta, f_small, content_w - 80), font=f_small, fill=TEXT_SUB)
            gy += 52

    # Bottom article lists
    article_y = group_y + group_h + 22
    article_h = 360
    aw = col_w

    def draw_article_panel(x: int, title: str, data: pd.DataFrame):
        _rounded(draw, (x, article_y, x + aw, article_y + article_h), radius=18)
        _section_header(draw, x, article_y, aw, title, f_section)
        if data is None or data.empty:
            draw.text((x + 18, article_y + 60), "표시할 기사가 없습니다.", font=f_body, fill=TEXT_SUB)
            return
        ay = article_y + 60
        for _, row in data.head(3).iterrows():
            cat = _safe(row.get("category", ""))
            source = _safe(row.get("source", ""))
            dt = _safe(row.get("date", ""))[5:].replace("-", ".") if _safe(row.get("date", "")) else ""
            tag_color = CATEGORY_COLORS.get(cat, BLUE)
            draw.rounded_rectangle((x + 16, ay, x + 86, ay + 24), radius=8, fill=tag_color)
            tag_text = _fit_text(cat, f_tag, 58)
            tw, _ = _text_size(f_tag, tag_text)
            draw.text((x + 51 - tw / 2, ay + 6), tag_text, font=f_tag, fill=WHITE)
            title_lines = _wrap_text(row.get("title", ""), f_bold, aw - 116, 2)
            draw.text((x + 100, ay), title_lines[0] if title_lines else "", font=f_bold, fill=TEXT)
            if len(title_lines) > 1:
                draw.text((x + 100, ay + 18), title_lines[1], font=f_bold, fill=TEXT)
                meta_y = ay + 38
            else:
                meta_y = ay + 22
            draw.text((x + 100, meta_y), _fit_text(source, f_small, aw - 170), font=f_small, fill=TEXT_SUB)
            dt_w, _ = _text_size(f_small, dt)
            draw.text((x + aw - 16 - dt_w, meta_y), dt, font=f_small, fill=TEXT_SUB)
            draw.line((x + 16, ay + 54, x + aw - 16, ay + 54), fill=LINE, width=1)
            ay += 92

    draw_article_panel(margin, "우선 확인 필요 기사", _priority_articles(df, limit=3))
    draw_article_panel(margin + aw + col_gap, "정책/공식자료 확인 기사", extract_policy_articles(df))

    # footer
    footer = "주의: 본 리포트는 Google News RSS 제목·요약 기반 자동 분류 결과이며, 최종 판단은 원문 및 규제기관 공식자료 확인이 필요합니다."
    draw.text((margin, H - 34), _fit_text(footer, f_small, W - margin*2 - 120), font=f_small, fill=TEXT_SUB)
    page = "1Page Report"
    pw, _ = _text_size(f_small, page)
    draw.text((W - margin - pw, H - 34), page, font=f_small, fill=TEXT_SUB)

    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def build_pdf_report(df: pd.DataFrame, issue_groups: list[dict] | None, start_date, end_date) -> bytes:
    """Wrap the fixed report PNG into a one-page PDF for stable layout."""
    png_bytes = build_report_png(df, issue_groups, start_date, end_date)
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    image = ImageReader(BytesIO(png_bytes))
    c.drawImage(image, 0, 0, width=width, height=height, preserveAspectRatio=True, mask='auto')
    c.showPage()
    c.save()
    return buffer.getvalue()
