from __future__ import annotations

import html
from typing import Iterable

import pandas as pd
import streamlit as st

from .classifier import category_palette


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root { --hanall-navy:#081f3f; --hanall-navy2:#102f59; --hanall-blue:#0065d8; --hanall-sky:#00a3d7; --hanall-teal:#00a6a6; --hanall-green:#68b545; --hanall-orange:#f47b20; --hanall-red:#d94d4d; --line:#d7e1ee; --soft:#f5f8fc; }
        .block-container { padding-top:1.0rem; padding-bottom:4rem; max-width:1500px; }
        header[data-testid="stHeader"] { background:rgba(255,255,255,0); }
        div[data-testid="stMetric"] { background:white; border:1px solid #dce7f4; border-radius:18px; padding:14px 16px; box-shadow:0 8px 18px rgba(8,31,63,0.06); }
        .hanall-header { padding:20px 24px; border-radius:24px; background:linear-gradient(135deg,#081f3f 0%,#123c68 100%); color:white; box-shadow:0 16px 34px rgba(8,31,63,0.14); margin-bottom:14px; position:relative; overflow:hidden; }
        .hanall-header::after { content:"HANALL BIOPHARMA"; position:absolute; right:22px; bottom:-8px; color:rgba(255,255,255,0.06); font-size:48px; font-weight:900; letter-spacing:-1px; }
        .hanall-header h1 { margin:0; font-size:30px; letter-spacing:-0.8px; }
        .hanall-header p { margin:7px 0 0; color:rgba(255,255,255,0.76); font-size:14px; }
        .compact-filter-title { font-weight:900; color:#081f3f; font-size:15px; margin:-2px 0 8px 0; }
        .small-caption { color:#64748b; font-size:12px; margin-top:-4px; }
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
        .link-row { display:flex; align-items:center; gap:8px; margin:6px 0 9px; }
        .icon-link { display:inline-flex; align-items:center; justify-content:center; min-width:92px; height:34px; padding:0 13px; border-radius:999px; border:1px solid #8db9ee; background:#eaf3ff; color:#005ec7 !important; font-weight:900; text-decoration:none !important; font-size:13px; white-space:nowrap; box-shadow:0 4px 10px rgba(0,101,216,0.10); }
        .icon-link:hover { background:#0065d8; color:#fff !important; border-color:#0065d8; }
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
        .policy-board-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-top:8px; }
        .board-link-card { display:flex; align-items:center; gap:10px; min-height:64px; padding:14px 16px; border:1px solid #dce7f4; border-radius:17px; background:linear-gradient(135deg,#ffffff,#f5f9ff); text-decoration:none !important; box-shadow:0 8px 18px rgba(8,31,63,0.045); }
        .board-link-card span { display:inline-grid; place-items:center; width:28px; height:28px; border-radius:10px; background:#eaf3ff; color:#0065d8; font-weight:900; }
        .board-link-card b { color:#081f3f; font-size:14px; }
        .board-link-card:hover { border-color:#9fc3ee; transform:translateY(-1px); }
        @media (max-width:1100px) { .kanban-wrap { grid-template-columns:repeat(2,minmax(0,1fr)); } .policy-board-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
        @media (max-width:760px) { .kanban-wrap { grid-template-columns:1fr; } .policy-board-grid { grid-template-columns:1fr; } .timeline-row { grid-template-columns:64px 18px minmax(0,1fr); } .hanall-header::after { display:none; } .stTabs [data-baseweb="tab"] { font-size:14px; padding:0 9px; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def title_with_link(title: object, link: object) -> str:
    safe_title = esc(title)
    safe_link = esc(link)
    title_html = f"<div class='news-title-row'><div class='news-title'>{safe_title}</div></div>"
    if safe_link:
        return title_html + f"<div class='link-row'><a class='icon-link' href='{safe_link}' target='_blank' rel='noopener noreferrer' title='원문 열기'>원문 열기 ↗</a></div>"
    return title_html + "<div class='link-row'><span class='missing-link'>링크 없음</span></div>"


def article_card(row: pd.Series, show_summary: bool = True) -> None:
    source = esc(row.get("source", ""))
    published = esc(row.get("published_at", ""))
    summary = esc(row.get("summary", ""))
    category = row.get("category", "산업/경영")
    importance = row.get("importance", "일반")
    keywords = [x.strip() for x in str(row.get("keywords", "")).split(",") if x.strip() and x.strip().lower() not in {"nan", "none"}][:5]
    keyword_html = "".join([f"<span class='tag'>{esc(x)}</span>" for x in keywords])
    summary_html = f"<div class='news-summary'>{summary[:180]}</div>" if show_summary and summary else ""
    title_html = title_with_link(row.get("title", ""), row.get("link", ""))
    html_block = f"<div class='news-card'><div class='news-meta'><span class='source-name'>{source}</span><span>{published}</span>{category_tag(category)}{importance_tag(importance)}</div>{title_html}{summary_html}<div>{keyword_html}</div></div>"
    st.markdown(html_block, unsafe_allow_html=True)


def timeline_item(row: pd.Series) -> None:
    time = esc(row.get("time", ""))
    source = esc(row.get("source", ""))
    published = esc(row.get("published_at", ""))
    category = row.get("category", "산업/경영")
    importance = row.get("importance", "일반")
    keywords = [x.strip() for x in str(row.get("keywords", "")).split(",") if x.strip() and x.strip().lower() not in {"nan", "none"}][:5]
    keyword_html = "".join([f"<span class='tag'>{esc(x)}</span>" for x in keywords])
    title_html = title_with_link(row.get("title", ""), row.get("link", ""))
    card = f"<div class='news-card'><div class='news-meta'><span class='source-name'>{source}</span><span>{published}</span>{category_tag(category)}{importance_tag(importance)}</div>{title_html}<div>{keyword_html}</div></div>"
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
