from __future__ import annotations

import base64
import hashlib
import html
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st

from .classifier import category_palette


def _asset_data_uri(filename: str) -> str:
    path = Path(__file__).resolve().parents[1] / "assets" / filename
    if not path.exists():
        return ""
    mime = "image/webp" if path.suffix.lower() == ".webp" else "image/png"
    try:
        return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")
    except Exception:
        return ""


def inject_css() -> None:
    summary_bg_uri = _asset_data_uri("summary_board.webp")
    summary_bg_css = f"background-image:url('{summary_bg_uri}');" if summary_bg_uri else "background:linear-gradient(135deg,#eef6ff,#ffffff);"
    css = """
        <style>
        :root { --hanall-navy:#081f3f; --hanall-navy2:#102f59; --hanall-blue:#0065d8; --hanall-sky:#00a3d7; --hanall-teal:#00a6a6; --hanall-green:#68b545; --hanall-orange:#f47b20; --hanall-red:#d94d4d; --line:#d7e1ee; --soft:#f5f8fc; }
        .block-container { padding-top:1.0rem; padding-bottom:4rem; max-width:1500px; }
        header[data-testid="stHeader"] { background:rgba(255,255,255,0); }
        div[data-testid="stMetric"] { background:white; border:1px solid #dce7f4; border-radius:18px; padding:14px 16px; box-shadow:0 8px 18px rgba(8,31,63,0.06); }
        .hanall-header { padding:20px 24px; border-radius:24px; background:linear-gradient(135deg,#081f3f 0%,#123c68 100%); color:white; box-shadow:0 16px 34px rgba(8,31,63,0.14); margin-bottom:14px; position:relative; overflow:hidden; }
        .hanall-header::after { content:"HANALL BIOPHARMA"; position:absolute; right:22px; bottom:-8px; color:rgba(255,255,255,0.14); font-size:48px; font-weight:900; letter-spacing:-1px; }
        .hanall-header h1 { margin:0; font-size:30px; letter-spacing:-0.8px; }
        .hanall-header p { margin:7px 0 0; color:rgba(255,255,255,0.76); font-size:14px; }
        .compact-filter-title { font-weight:900; color:#081f3f; font-size:15px; margin:-2px 0 8px 0; }
        .small-caption { color:#64748b; font-size:12px; margin-top:-4px; }

        .tab-button-spacer { height:8px; margin-top:2px; }
        div[data-testid="stButton"] > button { font-size:17px !important; font-weight:900 !important; border-radius:14px !important; min-height:46px; }
        div[data-testid="stButton"] > button p { font-size:17px !important; font-weight:900 !important; }
        div[data-testid="stHorizontalBlock"] div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"] { margin-bottom:0.15rem; }
        .stTabs [data-baseweb="tab-list"] { gap:10px; border-bottom:1px solid #dbe7f3; }
        .stTabs [data-baseweb="tab"] { height:48px; padding:0 18px; border-radius:14px 14px 0 0; font-size:17px; font-weight:900; color:#123c68; background:#f5f9ff; border:1px solid #dbe7f3; border-bottom:0; }
        .stTabs [aria-selected="true"] { background:#081f3f !important; color:white !important; }
        .section-title { display:flex; align-items:center; justify-content:space-between; margin:8px 0 12px; padding:0 2px; }
        .section-title h3 { margin:0; color:#081f3f; font-size:26px; font-weight:900; letter-spacing:-0.3px; }
        .section-title.compact h3 { color:#0b213d; font-size:20px; line-height:1.48; }
        .section-title span { color:#64748b; font-size:12px; }
        .news-card { background:#ffffff; border:1px solid #dce7f4; border-radius:18px; padding:19px 20px; margin-bottom:12px; box-shadow:0 8px 18px rgba(8,31,63,0.045); }
        .news-card:hover { border-color:#bcd4ef; box-shadow:0 12px 24px rgba(8,31,63,0.09); }
        .news-meta { display:flex; align-items:center; gap:8px; flex-wrap:wrap; color:#64748b; font-size:12px; margin-bottom:8px; }
        .source-name { color:#0065d8; font-weight:800; }
        .news-title { color:#0b213d; font-size:20px; font-weight:900; line-height:1.48; letter-spacing:-0.25px; }
        .news-title-row { display:block; margin-bottom:7px; }
        .news-title-row .news-title { width:100%; min-width:0; }
        .title-link { color:#0b213d !important; text-decoration:none; }
        .title-link:hover { color:#0065d8 !important; text-decoration:underline; }
        .link-row { display:flex; align-items:center; gap:8px; margin:6px 0 9px; flex-wrap:wrap; }
        .icon-link { display:inline-flex; align-items:center; justify-content:center; min-width:92px; height:34px; padding:0 13px; border-radius:999px; border:1px solid #8db9ee; background:#eaf3ff; color:#005ec7 !important; font-weight:900; text-decoration:none !important; font-size:13px; white-space:nowrap; box-shadow:0 4px 10px rgba(0,101,216,0.10); }
        .icon-link:hover { background:#0065d8; color:#fff !important; border-color:#0065d8; }
        .summary-open-btn { display:inline-flex; align-items:center; justify-content:center; min-width:116px; height:34px; padding:0 13px; border-radius:999px; border:1px solid #b8c7da; background:#f8fbff; color:#0b3b6d; font-weight:900; font-size:13px; cursor:pointer; box-shadow:0 4px 10px rgba(8,31,63,0.06); }
        .summary-open-btn:hover { background:#081f3f; color:#fff; border-color:#081f3f; }
        .summary-popover { width:min(1120px,94vw); height:min(760px,88vh); border:0; border-radius:26px; padding:0; overflow:hidden; box-shadow:0 28px 80px rgba(8,31,63,0.35); background:#fff; __SUMMARY_BOARD_BG__ background-size:cover; background-position:center; }
        .summary-popover::backdrop { background:rgba(5,20,40,0.48); backdrop-filter:blur(2px); }
        .summary-close-btn { position:absolute; right:22px; top:18px; z-index:4; border:1px solid #d7e1ee; background:rgba(255,255,255,0.92); color:#081f3f; border-radius:999px; height:34px; padding:0 14px; font-weight:900; cursor:pointer; box-shadow:0 4px 12px rgba(8,31,63,0.12); }
        .summary-board-text { position:absolute; left:34%; top:10.5%; width:57%; height:76%; padding:22px 28px; overflow:auto; color:#0b213d; }
        .summary-board-text h4 { margin:0 0 8px; color:#081f3f; font-size:22px; line-height:1.35; font-weight:900; letter-spacing:-0.35px; }
        .summary-board-meta { color:#5e7189; font-size:12px; font-weight:800; margin-bottom:14px; display:flex; gap:8px; flex-wrap:wrap; }
        .summary-board-text ul { margin:12px 0 0; padding-left:20px; }
        .summary-board-text li { margin-bottom:10px; line-height:1.62; font-size:15px; font-weight:750; }
        .summary-status { display:inline-block; margin-top:10px; color:#64748b; font-size:12px; font-weight:800; }
        .classification-reason { margin-top:12px; padding:9px 11px; border-radius:12px; background:rgba(255,255,255,0.72); border:1px dashed #b6c8dd; color:#49627d; font-size:12px; line-height:1.5; }
        @media (max-width:900px) { .summary-popover { background-image:none !important; background:linear-gradient(135deg,#ffffff,#eef6ff) !important; } .summary-board-text { left:5%; top:8%; width:90%; height:82%; padding:18px; } }
        .missing-link { display:inline-flex; align-items:center; justify-content:center; min-width:82px; height:30px; padding:0 12px; border-radius:999px; border:1px solid #d7e1ee; background:#f2f5f9; color:#7a8796; font-weight:900; font-size:12px; }
        .news-summary { color:#54657b; font-size:13px; line-height:1.55; margin-bottom:10px; }
        .tag { display:inline-flex; align-items:center; border-radius:999px; padding:4px 8px; font-size:11px; font-weight:800; border:1px solid rgba(0,0,0,0.08); background:#eef6ff; color:#0065d8; margin-right:4px; margin-bottom:4px; }
        .tag.high { background:#fff0f0; color:#d94d4d; }
        .tag.mid { background:#fff5e5; color:#bd6f00; }
        .tag.normal { background:#edf8ef; color:#2f8f40; }
        .open-link { display:inline-block; color:#0065d8 !important; font-weight:800; text-decoration:none; font-size:12px; margin-top:4px; }
        .kpi-card { background:white; border:1px solid #dce7f4; border-radius:20px; padding:15px 17px; min-height:104px; box-shadow:0 10px 22px rgba(8,31,63,0.06); }
        .kpi-label { color:#64748b; font-weight:800; font-size:13px; }
        .kpi-value { color:#081f3f; font-size:29px; font-weight:900; margin-top:8px; letter-spacing:-0.8px; }
        .kpi-sub { color:#00a65a; font-size:12px; font-weight:800; margin-top:6px; }
        .timeline-row { display:grid; grid-template-columns:92px 22px minmax(0,1fr); gap:10px; margin-bottom:10px; }
        .timeline-time { text-align:right; color:#64748b; font-size:12px; font-weight:900; padding-top:14px; }
        .timeline-pin { width:13px; height:13px; border-radius:50%; background:#0065d8; margin-top:15px; box-shadow:0 0 0 6px #eaf3ff; position:relative; }
        .timeline-pin::after { content:""; position:absolute; left:6px; top:13px; width:2px; height:86px; background:#dbe7f3; }
        .kanban-wrap { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }
        .kanban-lane { background:#f8fbff; border:1px solid #dce7f4; border-radius:20px; padding:12px; min-height:320px; }
        .kanban-head { display:flex; justify-content:space-between; align-items:center; margin:0 2px 12px; }
        .kanban-head b { color:#081f3f; font-size:15px; }
        .kanban-count { background:white; border:1px solid #dce7f4; color:#0065d8; border-radius:999px; padding:4px 10px; font-size:12px; font-weight:900; }
        .keyword-pill { display:inline-flex; padding:8px 12px; border-radius:999px; border:1px solid #d7e1ee; background:white; color:#081f3f; font-size:12px; font-weight:800; margin:0 6px 8px 0; }
        .policy-box { background:#fff; border:1px solid #dce7f4; border-left:5px solid #7b61ff; border-radius:18px; padding:20px 22px; margin-bottom:12px; box-shadow:0 8px 18px rgba(8,31,63,0.045); }
        .policy-box.wide { width:100%; }
        .policy-links a { display:inline-block; margin:4px 8px 2px 0; padding:5px 9px; border-radius:999px; border:1px solid #d7e1ee; color:#0065d8 !important; font-size:12px; text-decoration:none; font-weight:800; background:#f8fbff; }

        .pretty-table-wrap { border:1px solid #dce7f4; border-radius:18px; overflow:hidden; background:#fff; box-shadow:0 8px 18px rgba(8,31,63,0.045); }
        .pretty-table { width:100%; border-collapse:separate; border-spacing:0; font-size:13px; }
        .pretty-table thead th { background:linear-gradient(180deg,#f3f8ff,#eaf3ff); color:#081f3f; font-weight:900; text-align:left; padding:12px 14px; border-bottom:1px solid #d7e1ee; }
        .pretty-table tbody td { padding:12px 14px; border-bottom:1px solid #edf3f9; color:#1f334a; vertical-align:top; line-height:1.45; }
        .pretty-table tbody tr:nth-child(even) td { background:#fbfdff; }
        .pretty-table tbody tr:hover td { background:#f4f9ff; }
        .pretty-table tbody tr:last-child td { border-bottom:0; }
        .issue-summary { background:linear-gradient(135deg,#f8fbff,#eef6ff); border:1px solid #d7e7fb; border-left:6px solid #0065d8; border-radius:20px; padding:18px 20px; margin:6px 0 18px; box-shadow:0 10px 22px rgba(8,31,63,0.05); color:#0b213d; font-size:15px; font-weight:700; line-height:1.75; }
        .issue-group-wrap { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; margin:4px 0 18px; }
        .issue-group-card { background:#fff; border:1px solid #dce7f4; border-radius:20px; padding:17px 18px; box-shadow:0 8px 18px rgba(8,31,63,0.045); }
        .issue-group-head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:8px; }
        .issue-group-head b { color:#0b213d; font-size:16px; line-height:1.45; font-weight:900; }
        .issue-group-head span { flex:0 0 auto; border-radius:999px; padding:5px 10px; background:#eef6ff; color:#0065d8; font-size:12px; font-weight:900; }
        .issue-group-meta { color:#64748b; font-size:12px; font-weight:700; margin-bottom:8px; }
        .issue-list { margin:8px 0 0 0; padding-left:18px; color:#1f334a; }
        .issue-list li { margin-bottom:7px; line-height:1.5; font-size:13px; }
        .issue-list li span { color:#0065d8; font-weight:900; margin-right:4px; }
        .issue-list a { color:#0b213d !important; text-decoration:none; font-weight:800; }
        .issue-list a:hover { color:#0065d8 !important; text-decoration:underline; }
        .policy-board-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-top:8px; }
        .board-link-card { display:flex; align-items:center; gap:10px; min-height:64px; padding:14px 16px; border:1px solid #dce7f4; border-radius:17px; background:linear-gradient(135deg,#ffffff,#f5f9ff); text-decoration:none !important; box-shadow:0 8px 18px rgba(8,31,63,0.045); }
        .board-link-card span { display:inline-grid; place-items:center; width:28px; height:28px; border-radius:10px; background:#eaf3ff; color:#0065d8; font-weight:900; }
        .board-link-card b { color:#081f3f; font-size:14px; }
        .board-link-card:hover { border-color:#9fc3ee; transform:translateY(-1px); }
        @media (max-width:1100px) { .kanban-wrap { grid-template-columns:repeat(2,minmax(0,1fr)); } .policy-board-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .issue-group-wrap { grid-template-columns:1fr; } }
        @media (max-width:760px) { .kanban-wrap { grid-template-columns:1fr; } .policy-board-grid { grid-template-columns:1fr; } .timeline-row { grid-template-columns:64px 18px minmax(0,1fr); } .hanall-header::after { display:none; } .stTabs [data-baseweb="tab"] { font-size:14px; padding:0 9px; } }
        </style>
        """
    css = css.replace("__SUMMARY_BOARD_BG__", summary_bg_css)
    st.markdown(css, unsafe_allow_html=True)


def esc(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    if text.strip().lower() in {"nan", "none", "nat", "null"}:
        return ""
    return html.escape(text, quote=True)


def header(title: str, subtitle: str) -> None:
    html_block = f"<div class='hanall-header'><h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div>"
    st.markdown(html_block, unsafe_allow_html=True)


def section_title(title: str, right: str = "", compact: bool = False) -> None:
    cls = "section-title compact" if compact else "section-title"
    st.markdown(f"<div class='{cls}'><h3>{esc(title)}</h3><span>{esc(right)}</span></div>", unsafe_allow_html=True)


def kpi_card(label: str, value: str, sub: str = "") -> None:
    html_block = f"<div class='kpi-card'><div class='kpi-label'>{esc(label)}</div><div class='kpi-value'>{esc(value)}</div><div class='kpi-sub'>{esc(sub)}</div></div>"
    st.markdown(html_block, unsafe_allow_html=True)


def category_tag(category: str) -> str:
    category = esc(category) or "산업/경영"
    colors = category_palette()
    color = colors.get(html.unescape(category), "#64748b")
    return f"<span class='tag' style='background:{color}18;color:{color};border-color:{color}44'>{category}</span>"


def importance_tag(importance: str) -> str:
    importance = esc(importance) or "일반"
    cls = "high" if importance == "높음" else "mid" if importance == "중간" else "normal"
    return f"<span class='tag {cls}'>중요도 {importance}</span>"


def _split_summary_lines(value: object) -> list[str]:
    raw = str(value or "")
    lines: list[str] = []
    for line in raw.replace("\r", "\n").split("\n"):
        clean = line.strip().strip("-• ").strip()
        if clean and clean.lower() not in {"nan", "none", "null"}:
            lines.append(clean)
    return lines


def _summary_popover_html(row: pd.Series, show_reason: bool = False) -> str:
    if row is None:
        return ""
    summary = row.get("article_summary", "") or row.get("summary", "")
    lines = _split_summary_lines(summary)
    if not lines:
        lines = ["요약 정보가 없습니다. 원문 열기를 통해 기사 본문을 확인해 주세요."]
    status = esc(row.get("body_fetch_status", ""))
    reason = esc(row.get("classification_reason", "")) if show_reason else ""
    title = esc(row.get("title", ""))
    source = esc(row.get("source", ""))
    published = esc(row.get("published_at", "")) or esc(row.get("time", ""))
    tags = [x.strip() for x in str(row.get("sub_tags", "")).split(",") if x.strip() and x.strip().lower() not in {"nan", "none"}][:5]
    tag_html = "".join([f"<span class='tag'>{esc(t)}</span>" for t in tags])
    reason_html = f"<div class='classification-reason'>분류근거: {reason}</div>" if reason else ""
    status_html = f"<span class='summary-status'>수집상태: {status}</span>" if status else ""
    list_html = "".join([f"<li>{esc(line)}</li>" for line in lines[:5]])
    uid_src = f"{row.get('uid','')}|{row.get('link','')}|{row.get('title','')}"
    pop_id = "summary_" + hashlib.md5(uid_src.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return (
        f"<button class='summary-open-btn' popovertarget='{pop_id}' type='button'>기사 요약 보기</button>"
        f"<div id='{pop_id}' popover class='summary-popover'>"
        f"<button class='summary-close-btn' popovertarget='{pop_id}' popovertargetaction='hide' type='button'>닫기 ×</button>"
        f"<div class='summary-board-text'><h4>{title}</h4>"
        f"<div class='summary-board-meta'><span>{source}</span><span>{published}</span></div>"
        f"<div>{tag_html}</div><ul>{list_html}</ul>{status_html}{reason_html}</div>"
        f"</div>"
    )

def title_with_link(title: object, link: object, row: pd.Series | None = None, show_reason: bool = False) -> str:
    safe_title = esc(title)
    safe_link = esc(link)
    title_html = f"<div class='news-title-row'><div class='news-title'>{safe_title}</div></div>"
    summary_html = _summary_popover_html(row, show_reason=show_reason) if row is not None else ""
    if safe_link:
        return title_html + f"<div class='link-row'><a class='icon-link' href='{safe_link}' target='_blank' rel='noopener noreferrer' title='원문 열기'>원문 열기 ↗</a>{summary_html}</div>"
    return title_html + f"<div class='link-row'><span class='missing-link'>링크 없음</span>{summary_html}</div>"


def article_card(row: pd.Series, show_summary: bool = True) -> None:
    source = esc(row.get("source", ""))
    published = esc(row.get("published_at", ""))
    summary = esc(row.get("summary", ""))
    category = row.get("category", "산업/경영")
    importance = row.get("importance", "일반")
    keywords = [x.strip() for x in str(row.get("keywords", "")).split(",") if x.strip() and x.strip().lower() not in {"nan", "none"}][:5]
    sub_tags = [x.strip() for x in str(row.get("sub_tags", "")).split(",") if x.strip() and x.strip().lower() not in {"nan", "none"}][:3]
    keyword_html = "".join([f"<span class='tag'>{esc(x)}</span>" for x in keywords])
    subtag_html = "".join([f"<span class='tag' style='background:#f8fbff;color:#475569;border-color:#cbd5e1'>{esc(x)}</span>" for x in sub_tags])
    summary_html = f"<div class='news-summary'>{summary[:180]}</div>" if show_summary and summary else ""
    title_html = title_with_link(row.get("title", ""), row.get("link", ""), row)
    html_block = f"<div class='news-card'><div class='news-meta'><span class='source-name'>{source}</span><span>{published}</span>{category_tag(category)}{importance_tag(importance)}</div>{title_html}{summary_html}<div>{subtag_html}{keyword_html}</div></div>"
    st.markdown(html_block, unsafe_allow_html=True)


def timeline_item(row: pd.Series) -> None:
    time = esc(row.get("time", ""))
    source = esc(row.get("source", ""))
    published = esc(row.get("published_at", ""))
    category = row.get("category", "산업/경영")
    importance = row.get("importance", "일반")
    keywords = [x.strip() for x in str(row.get("keywords", "")).split(",") if x.strip() and x.strip().lower() not in {"nan", "none"}][:5]
    sub_tags = [x.strip() for x in str(row.get("sub_tags", "")).split(",") if x.strip() and x.strip().lower() not in {"nan", "none"}][:3]
    keyword_html = "".join([f"<span class='tag'>{esc(x)}</span>" for x in keywords])
    subtag_html = "".join([f"<span class='tag' style='background:#f8fbff;color:#475569;border-color:#cbd5e1'>{esc(x)}</span>" for x in sub_tags])
    title_html = title_with_link(row.get("title", ""), row.get("link", ""), row)
    card = f"<div class='news-card'><div class='news-meta'><span class='source-name'>{source}</span><span>{published}</span>{category_tag(category)}{importance_tag(importance)}</div>{title_html}<div>{subtag_html}{keyword_html}</div></div>"
    html_block = f"<div class='timeline-row'><div class='timeline-time'>{time}</div><div class='timeline-pin'></div>{card}</div>"
    st.markdown(html_block, unsafe_allow_html=True)


def keyword_pills(keywords: Iterable[tuple[str, int]]) -> None:
    html_parts = []
    for kw, count in keywords:
        if not str(kw).strip() or str(kw).strip().lower() in {"nan", "none"}:
            continue
        html_parts.append(f"<span class='keyword-pill'>#{esc(kw)} <b style='margin-left:6px;color:#0065d8'>{count}</b></span>")
    if html_parts:
        st.markdown("".join(html_parts), unsafe_allow_html=True)
