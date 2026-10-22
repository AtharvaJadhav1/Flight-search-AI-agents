"""Theme, CSS and HTML render helpers for the Streamlit UI."""

from __future__ import annotations

from html import escape
from typing import Any, Dict, List, Optional

import streamlit as st

from tools import format_inr, parse_duration_minutes

WORKFLOW_STEPS = ["Parse", "Memory", "Plan", "Search", "Analyze", "Approve", "Email"]

BASE_CSS = """
:root {
  --bg: #F5F7FB; --surface: #FFFFFF; --surface-2: #F1F5F9; --border: #E2E8F0;
  --text: #0F172A; --muted: #64748B; --accent: #2563EB; --accent-soft: #EAF1FF;
  --accent-text: #1D4ED8; --good: #059669; --good-soft: #E7F8F1; --warn: #B45309;
  --warn-soft: #FEF3E2; --bad: #DC2626; --bad-soft: #FDECEC; --shadow: 0 1px 2px rgba(15,23,42,.06);
}

.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { background: var(--bg) !important; }
header[data-testid="stHeader"] { background: transparent !important; }
.block-container { max-width: 1120px; padding: 1.4rem 1.25rem 3rem; }
[data-testid="stSidebar"] { background: var(--surface) !important; border-right: 1px solid var(--border); }
[data-testid="stSidebar"] .block-container, [data-testid="stSidebarContent"] { padding-top: 1rem; }

.stApp, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
[data-testid="stMarkdownContainer"] p, [data-testid="stWidgetLabel"] p {
  color: var(--text);
}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p, .stApp small { color: var(--muted) !important; }

/* Inputs */
.stTextArea textarea, .stTextInput input, [data-baseweb="select"] > div, [data-baseweb="input"] {
  background: var(--surface) !important; color: var(--text) !important;
  border: 1px solid var(--border) !important; border-radius: 10px !important;
}
.stTextArea textarea::placeholder, .stTextInput input::placeholder { color: var(--muted) !important; opacity: .8; }
.stTextArea textarea:focus, .stTextInput input:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 3px var(--accent-soft) !important; }
[data-baseweb="popover"] *, [data-baseweb="menu"] * { color: var(--text); background: var(--surface); }
[data-testid="stCheckbox"] span, [data-testid="stToggle"] span { color: var(--text); }

/* Buttons */
.stButton button, .stDownloadButton button {
  border-radius: 10px; border: 1px solid var(--border); background: var(--surface);
  color: var(--text); font-weight: 600; padding: .5rem 1rem; box-shadow: var(--shadow);
  transition: border-color .15s, transform .05s;
}
.stButton button:hover, .stDownloadButton button:hover { border-color: var(--accent); color: var(--accent-text); }
.stButton button:active { transform: translateY(1px); }
.stButton button[kind="primary"], .stButton button[data-testid="stBaseButton-primary"] {
  background: var(--accent); border-color: var(--accent); color: #fff;
}
.stButton button[kind="primary"]:hover, .stButton button[data-testid="stBaseButton-primary"]:hover { filter: brightness(1.08); color: #fff; }
.stButton button p, .stDownloadButton button p { color: inherit !important; }
[class*="st-key-chip_"] button { font-weight: 500; font-size: .82rem; padding: .3rem .75rem; border-radius: 999px; background: var(--surface-2); box-shadow: none; }

[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] .stTextArea) {
  background: var(--surface); border-color: var(--border) !important; border-radius: 14px; box-shadow: var(--shadow);
}
[class*="st-key-chip_"] button p { white-space: normal; line-height: 1.25; }

/* Tabs / expanders */
[data-baseweb="tab-list"] { gap: .25rem; border-bottom: 1px solid var(--border); }
[data-baseweb="tab"] { color: var(--muted) !important; font-weight: 600; background: transparent !important; }
[data-baseweb="tab"][aria-selected="true"] { color: var(--accent-text) !important; }
[data-baseweb="tab-highlight"] { background: var(--accent) !important; }
[data-testid="stExpander"] { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; }
[data-testid="stExpander"] summary p { color: var(--text); font-weight: 600; }

/* Hero */
.hero { display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem; }
.hero-title { display: flex; align-items: center; gap: .75rem; }
.logo { width: 42px; height: 42px; border-radius: 12px; display: grid; place-items: center; font-size: 1.35rem;
  background: linear-gradient(135deg, var(--accent), #7C3AED); color: #fff; }
.hero .app-title { font-size: 1.55rem; font-weight: 750; margin: 0; line-height: 1.15; letter-spacing: -.01em; color: var(--text); }
.hero .app-sub { color: var(--muted); font-size: .9rem; margin: .15rem 0 0; }
.pill { display: inline-flex; align-items: center; gap: .35rem; font-size: .75rem; font-weight: 650; padding: .28rem .7rem;
  border-radius: 999px; border: 1px solid var(--border); background: var(--surface); color: var(--muted); }
.pill.demo { background: var(--warn-soft); color: var(--warn); border-color: transparent; }
.pill.live { background: var(--good-soft); color: var(--good); border-color: transparent; }

/* Cards */
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 1.1rem 1.2rem; box-shadow: var(--shadow); }
.section-label { font-size: .72rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); margin: 1.2rem 0 .5rem; }

/* Stepper */
.stepper { display: flex; gap: .35rem; overflow-x: auto; padding: .15rem 0 .35rem; margin: .25rem 0 .5rem; scrollbar-width: thin; }
.step { flex: 1 0 auto; display: flex; align-items: center; gap: .45rem; font-size: .78rem; font-weight: 600; white-space: nowrap;
  padding: .4rem .75rem; border-radius: 999px; border: 1px solid var(--border); background: var(--surface); color: var(--muted); }
.step .dot { width: 18px; height: 18px; border-radius: 50%; display: grid; place-items: center; font-size: .65rem; background: var(--surface-2); color: var(--muted); }
.step.done { color: var(--accent-text); background: var(--accent-soft); border-color: transparent; }
.step.done .dot { background: var(--accent); color: #fff; }
.step.active { color: #fff; background: var(--accent); border-color: var(--accent); }
.step.active .dot { background: rgba(255,255,255,.25); color: #fff; }
.step.fail { color: var(--bad); background: var(--bad-soft); border-color: transparent; }
.step.fail .dot { background: var(--bad); color: #fff; }

/* KPIs */
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: .75rem; margin: .5rem 0 .25rem; }
.kpi { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: .8rem 1rem; box-shadow: var(--shadow); min-width: 0; }
.kpi .label { font-size: .72rem; color: var(--muted); font-weight: 650; text-transform: uppercase; letter-spacing: .06em; }
.kpi .value { font-size: 1.2rem; font-weight: 750; margin-top: .15rem; line-height: 1.25; overflow-wrap: anywhere; color: var(--text); }
.kpi .hint { font-size: .78rem; color: var(--good); font-weight: 600; }

/* Flight cards */
.flights { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: .85rem; }
.flight-card { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 1rem 1.1rem; box-shadow: var(--shadow); position: relative; }
.flight-card.best { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }
.fc-top { display: flex; justify-content: space-between; align-items: flex-start; gap: .75rem; }
.fc-rank { font-size: .72rem; font-weight: 700; color: var(--accent-text); letter-spacing: .05em; }
.fc-airline { font-size: 1.02rem; font-weight: 700; color: var(--text); margin-top: .1rem; }
.fc-num { font-size: .8rem; color: var(--muted); }
.fc-price { font-size: 1.35rem; font-weight: 800; color: var(--accent-text); text-align: right; white-space: nowrap; }
.fc-save { font-size: .74rem; color: var(--good); font-weight: 650; text-align: right; }
.fc-route { display: flex; align-items: center; gap: .6rem; margin: .8rem 0 .6rem; }
.fc-time { font-weight: 700; font-size: .95rem; color: var(--text); }
.fc-line { flex: 1; height: 2px; background: var(--border); position: relative; border-radius: 2px; }
.fc-line::after { content: "✈"; position: absolute; left: 50%; top: -9px; transform: translateX(-50%); background: var(--surface); padding: 0 .3rem; font-size: .75rem; color: var(--muted); }
.fc-meta { display: flex; flex-wrap: wrap; gap: .35rem; }
.tag { font-size: .72rem; font-weight: 650; padding: .2rem .55rem; border-radius: 999px; background: var(--surface-2); color: var(--muted); }
.tag.good { background: var(--good-soft); color: var(--good); }
.tag.accent { background: var(--accent-soft); color: var(--accent-text); }

/* Table */
.table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: 14px; background: var(--surface); }
table.ft { width: 100%; border-collapse: collapse; font-size: .85rem; min-width: 640px; }
table.ft th { text-align: left; font-size: .7rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); padding: .65rem .8rem; border-bottom: 1px solid var(--border); background: var(--surface-2); }
table.ft td { padding: .65rem .8rem; border-bottom: 1px solid var(--border); color: var(--text); }
table.ft tr:last-child td { border-bottom: none; }
table.ft td.num { text-align: right; font-variant-numeric: tabular-nums; font-weight: 650; }
table.ft tr.over td { color: var(--muted); }

/* Bar chart */
.bars { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 1rem 1.2rem; }
.bar-row { display: grid; grid-template-columns: minmax(90px, 160px) 1fr 84px; gap: .75rem; align-items: center; margin: .45rem 0; font-size: .82rem; }
.bar-name { color: var(--text); font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-track { position: relative; height: 12px; background: var(--surface-2); border-radius: 999px; }
.bar-fill { height: 100%; border-radius: 999px; background: var(--accent); }
.bar-fill.over { background: var(--border); }
.bar-fill.picked { background: var(--good); }
.bar-budget { position: absolute; top: -4px; bottom: -4px; width: 2px; background: var(--bad); border-radius: 2px; }
.bar-val { text-align: right; font-weight: 650; font-variant-numeric: tabular-nums; color: var(--text); }
.legend { display: flex; flex-wrap: wrap; gap: .9rem; font-size: .74rem; color: var(--muted); margin-top: .6rem; }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: .3rem; vertical-align: -1px; }

/* Notices, timeline */
.notice { border-radius: 12px; padding: .8rem 1rem; font-size: .9rem; margin: .5rem 0; border: 1px solid transparent; }
.notice.info { background: var(--accent-soft); color: var(--accent-text); }
.notice.warn { background: var(--warn-soft); color: var(--warn); }
.notice.bad { background: var(--bad-soft); color: var(--bad); }
.notice.good { background: var(--good-soft); color: var(--good); }
.notice b { font-weight: 700; }
.timeline { border-left: 2px solid var(--border); margin: .4rem 0 .2rem .5rem; padding-left: 1rem; }
.tl-item { position: relative; margin-bottom: .85rem; }
.tl-item::before { content: ""; position: absolute; left: -1.38rem; top: .3rem; width: 10px; height: 10px; border-radius: 50%; background: var(--accent); border: 2px solid var(--bg); }
.tl-agent { font-weight: 700; font-size: .85rem; color: var(--text); }
.tl-detail { font-size: .82rem; color: var(--muted); }
.mem-row { display: flex; justify-content: space-between; gap: .5rem; font-size: .85rem; padding: .3rem 0; border-bottom: 1px dashed var(--border); }
.mem-row span:first-child { color: var(--muted); }
.mem-row span:last-child { color: var(--text); font-weight: 600; text-align: right; }
.mail { white-space: pre-wrap; font-family: ui-monospace, Menlo, Consolas, monospace; font-size: .82rem; line-height: 1.55; background: var(--surface-2); color: var(--text); border-radius: 10px; padding: .9rem 1rem; }
.empty p { color: var(--muted); margin: .25rem 0; }
.empty { text-align: center; padding: 2.2rem 1rem; color: var(--muted); }
.empty .big { font-size: 2rem; }
.empty p b { color: var(--text); }

@media (max-width: 760px) {
  .block-container { padding: .9rem .75rem 2.5rem; }
  .kpis { grid-template-columns: repeat(2, 1fr); }
  .flights { grid-template-columns: 1fr; }
  .hero .app-title { font-size: 1.3rem; }
  .bar-row { grid-template-columns: 82px 1fr 70px; gap: .5rem; }
}
"""


def inject_streamlit_css(dark: bool = False) -> None:
    """Inject theme variables. `dark` toggles the dark palette on the app root."""
    marker = ":root" if dark else ":root:not(:root)"
    dark_rule = f"{marker} {{ --bg:#0B1220; --surface:#111A2E; --surface-2:#172138; --border:#24324D; --text:#E8EEF9; --muted:#9AA8C2; --accent:#4F8BFF; --accent-soft:#14233F; --accent-text:#9CC0FF; --good:#34D399; --good-soft:#0F2A24; --warn:#FBBF24; --warn-soft:#2D2410; --bad:#F87171; --bad-soft:#321517; --shadow:none; }}"
    st.markdown(f"<style>{BASE_CSS}\n{dark_rule}</style>", unsafe_allow_html=True)


def render_header(demo_mode: bool) -> None:
    pill = (
        '<span class="pill demo">● Demo mode · offline</span>'
        if demo_mode
        else '<span class="pill live">● Live · LLM parsing</span>'
    )
    st.markdown(
        f"""
<div class="hero">
  <div class="hero-title">
    <div class="logo">✈</div>
    <div>
      <p class="app-title">Flight Search AI Agent</p>
      <p class="app-sub">Describe a trip in plain English — the agent searches, filters, and drafts the email for your approval.</p>
    </div>
  </div>
  <div>{pill}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def section(label: str) -> None:
    st.markdown(f'<div class="section-label">{escape(label)}</div>', unsafe_allow_html=True)


def notice(kind: str, text: str) -> None:
    st.markdown(f'<div class="notice {kind}">{text}</div>', unsafe_allow_html=True)


def stepper_states(status: str, awaiting: bool) -> List[str]:
    """Return one of wait/done/active/fail for each workflow step."""
    n = len(WORKFLOW_STEPS)
    states = ["wait"] * n
    if not status:
        return states

    def fill(done: int, active: Optional[int] = None, fail: Optional[int] = None) -> List[str]:
        out = ["wait"] * n
        for i in range(done):
            out[i] = "done"
        if active is not None:
            out[active] = "active"
        if fail is not None:
            out[fail] = "fail"
        return out

    if status == "missing_info":
        return fill(0, fail=0)
    if status == "no_flights":
        return fill(4, fail=4)
    if status == "error":
        return fill(0, fail=0)
    if status == "rejected":
        return fill(5, fail=5)
    if status == "approved":
        return fill(6, active=6)
    if status == "completed":
        return fill(n)
    return fill(5, active=5)  # analyzed → waiting on the human


def render_stepper(status: str, awaiting: bool) -> None:
    chips = []
    for index, (label, state) in enumerate(zip(WORKFLOW_STEPS, stepper_states(status, awaiting)), start=1):
        icon = {"done": "✓", "fail": "!", "active": "●"}.get(state, str(index))
        chips.append(f'<span class="step {state}"><span class="dot">{icon}</span>{label}</span>')
    st.markdown(f'<div class="stepper">{"".join(chips)}</div>', unsafe_allow_html=True)


def render_kpis(result: Dict[str, Any]) -> None:
    selected = result.get("selected_flights") or []
    budget = result.get("budget") or 0
    best = min((f["price"] for f in selected), default=None)
    save_hint = f"Saves {format_inr(budget - best)} vs budget" if best is not None and budget else ""
    total = len(result.get("all_flights") or [])
    route = f'{escape(str(result.get("source") or "—"))} → {escape(str(result.get("destination") or "—"))}'
    st.markdown(
        f"""
<div class="kpis">
  <div class="kpi"><div class="label">Route</div><div class="value">{route}</div></div>
  <div class="kpi"><div class="label">Budget</div><div class="value">{format_inr(budget) if budget else "—"}</div></div>
  <div class="kpi"><div class="label">Best price</div><div class="value">{format_inr(best) if best is not None else "—"}</div><div class="hint">{save_hint}</div></div>
  <div class="kpi"><div class="label">Matches</div><div class="value">{len(selected)} of {total}</div></div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_flight_cards(selected: List[dict], budget: int = 0) -> None:
    if not selected:
        return
    cheapest = min(f["price"] for f in selected)
    fastest = min(parse_duration_minutes(f["duration"]) for f in selected)
    cards = []
    for index, f in enumerate(selected, start=1):
        tags = []
        if f["price"] == cheapest:
            tags.append('<span class="tag good">Cheapest</span>')
        if parse_duration_minutes(f["duration"]) == fastest:
            tags.append('<span class="tag accent">Fastest</span>')
        stops = "Nonstop" if f["stops"] == 0 else f'{f["stops"]} stop{"s" if f["stops"] != 1 else ""}'
        tags.append(f'<span class="tag">{stops}</span>')
        tags.append(f'<span class="tag">{escape(f["duration"])}</span>')
        save = f'<div class="fc-save">{format_inr(budget - f["price"])} under budget</div>' if budget else ""
        cards.append(
            f"""
<div class="flight-card{" best" if index == 1 else ""}">
  <div class="fc-top">
    <div><div class="fc-rank">OPTION {index}</div>
      <div class="fc-airline">{escape(f["airline"])}</div>
      <div class="fc-num">{escape(f["flight_number"])}</div></div>
    <div><div class="fc-price">{format_inr(f["price"])}</div>{save}</div>
  </div>
  <div class="fc-route"><span class="fc-time">{escape(f["departure"])}</span><span class="fc-line"></span><span class="fc-time">{escape(f["arrival"])}</span></div>
  <div class="fc-meta">{"".join(tags)}</div>
</div>"""
        )
    st.markdown(f'<div class="flights">{"".join(cards)}</div>', unsafe_allow_html=True)


def flight_status(flight: dict, result: Dict[str, Any]) -> str:
    selected_numbers = {f["flight_number"] for f in result.get("selected_flights") or []}
    if flight["flight_number"] in selected_numbers:
        return "Selected"
    if flight["price"] > (result.get("budget") or 0):
        return "Over budget"
    return "Filtered"


def render_all_flights_table(result: Dict[str, Any]) -> None:
    rows = []
    for f in sorted(result.get("all_flights") or [], key=lambda x: x["price"]):
        status = flight_status(f, result)
        cls = "over" if status != "Selected" else ""
        tag = {"Selected": "good", "Over budget": "", "Filtered": ""}[status]
        stops = "Nonstop" if f["stops"] == 0 else f'{f["stops"]} stop'
        rows.append(
            f'<tr class="{cls}"><td>{escape(f["airline"])}</td><td>{escape(f["flight_number"])}</td>'
            f'<td>{escape(f["departure"])} → {escape(f["arrival"])}</td><td>{escape(f["duration"])}</td>'
            f'<td>{stops}</td><td class="num">{format_inr(f["price"])}</td>'
            f'<td><span class="tag {tag}">{status}</span></td></tr>'
        )
    st.markdown(
        '<div class="table-wrap"><table class="ft"><thead><tr><th>Airline</th><th>Flight</th><th>Times</th>'
        '<th>Duration</th><th>Stops</th><th style="text-align:right">Price</th><th>Status</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>',
        unsafe_allow_html=True,
    )


def render_price_chart(result: Dict[str, Any]) -> None:
    flights = sorted(result.get("all_flights") or [], key=lambda x: x["price"])
    if not flights:
        return
    budget = result.get("budget") or 0
    top = max(max(f["price"] for f in flights), budget) * 1.05
    selected_numbers = {f["flight_number"] for f in result.get("selected_flights") or []}
    rows = []
    for f in flights:
        cls = "picked" if f["flight_number"] in selected_numbers else ("over" if f["price"] > budget else "")
        width = f["price"] / top * 100
        marker = f'<span class="bar-budget" style="left:{budget / top * 100:.1f}%"></span>' if budget else ""
        rows.append(
            f'<div class="bar-row"><div class="bar-name">{escape(f["airline"])}</div>'
            f'<div class="bar-track"><div class="bar-fill {cls}" style="width:{width:.1f}%"></div>{marker}</div>'
            f'<div class="bar-val">{format_inr(f["price"])}</div></div>'
        )
    st.markdown(
        f'<div class="bars">{"".join(rows)}<div class="legend">'
        '<span><i style="background:var(--good)"></i>Selected</span>'
        '<span><i style="background:var(--accent)"></i>Within budget</span>'
        '<span><i style="background:var(--border)"></i>Over budget</span>'
        '<span><i style="background:var(--bad)"></i>Your budget</span></div></div>',
        unsafe_allow_html=True,
    )


def render_timeline(trace: List[Dict[str, str]]) -> None:
    if not trace:
        st.caption("No activity yet.")
        return
    items = "".join(
        f'<div class="tl-item"><div class="tl-agent">{escape(t["agent"])}</div>'
        f'<div class="tl-detail">{escape(t["detail"])}</div></div>'
        for t in trace
    )
    st.markdown(f'<div class="timeline">{items}</div>', unsafe_allow_html=True)


def render_memory_panel(memory: Dict[str, Any]) -> None:
    budget = memory.get("budget")
    route = (
        f'{memory["source"]} → {memory["destination"]}'
        if memory.get("source") and memory.get("destination")
        else "—"
    )
    rows = [
        ("Route", route),
        ("Budget", format_inr(budget) if budget else "—"),
        ("Top results", str(memory.get("top_results") or 3)),
        ("Last results", "Saved" if memory.get("has_previous_results") else "None"),
    ]
    html = "".join(
        f'<div class="mem-row"><span>{escape(k)}</span><span>{escape(v)}</span></div>' for k, v in rows
    )
    st.markdown(html, unsafe_allow_html=True)


def render_empty_state() -> None:
    st.markdown(
        '<div class="card empty"><div class="big">🛫</div>'
        "<p><b>Ready when you are</b></p>"
        "<p>Type a request above or pick an example. Results, the agent's activity log, "
        "and the approval step will appear here.</p></div>",
        unsafe_allow_html=True,
    )
