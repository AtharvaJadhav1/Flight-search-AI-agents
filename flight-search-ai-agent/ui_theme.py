"""Shared UI styling for Streamlit."""

from __future__ import annotations

from typing import List, Optional

import streamlit as st

from tools import format_inr

WORKFLOW_STEPS = [
    ("parse_request", "Parser"),
    ("apply_memory", "Memory"),
    ("create_plan", "Plan"),
    ("search_flights", "Search"),
    ("analyze_flights", "Analysis"),
    ("human_approval", "Approve"),
    ("generate_email", "Email"),
]

LIGHT_CSS = """
  .block-container { padding-top: 1.25rem; padding-bottom: 1.5rem; max-width: 1080px; }
  header[data-testid="stHeader"] { background: transparent; }
  div[data-testid="stMetricValue"] { font-size: 1.25rem; font-weight: 600; }
  .app-title { font-size: 1.65rem; font-weight: 700; color: #0F172A; margin: 0; line-height: 1.2; }
  .app-sub { color: #64748B; font-size: 0.9rem; margin: 0.25rem 0 0; }
  .flight-card {
    border: 1px solid #E2E8F0; border-radius: 12px; padding: 1rem 1.1rem;
    background: #FFFFFF; margin-bottom: 0.65rem;
  }
  .flight-card .rank { color: #1D4ED8; font-weight: 700; font-size: 0.8rem; }
  .flight-card .airline { font-size: 1.05rem; font-weight: 600; color: #0F172A; margin: 0.1rem 0; }
  .flight-card .price { font-size: 1.2rem; font-weight: 700; color: #1D4ED8; }
  .flight-card .meta { color: #64748B; font-size: 0.86rem; }
  .stepper { display: flex; flex-wrap: wrap; gap: 0.3rem; margin: 0.35rem 0 0.75rem; }
  .step {
    font-size: 0.75rem; padding: 0.32rem 0.6rem; border-radius: 999px;
    border: 1px solid #E2E8F0; background: #F8FAFC; color: #64748B;
  }
  .step.done { background: #EEF2FF; border-color: #C7D2FE; color: #1D4ED8; font-weight: 600; }
  .step.active { background: #1D4ED8; border-color: #1D4ED8; color: #fff; font-weight: 600; }
  .approval-box {
    border: 1px solid #C7D2FE; background: #F8FAFF; border-radius: 12px;
    padding: 0.85rem 1rem; margin: 0.5rem 0 0.75rem; color: #334155; font-size: 0.9rem;
  }
"""

DARK_CSS = """
  .stApp, [data-testid="stAppViewContainer"] { background-color: #0B1220 !important; }
  .block-container { padding-top: 1.25rem; padding-bottom: 1.5rem; max-width: 1080px; }
  header[data-testid="stHeader"] { background: transparent; }
  .app-title { font-size: 1.65rem; font-weight: 700; color: #F1F5F9; margin: 0; }
  .app-sub { color: #94A3B8; font-size: 0.9rem; margin: 0.25rem 0 0; }
  .flight-card {
    border: 1px solid #1E293B; border-radius: 12px; padding: 1rem 1.1rem;
    background: #111827; margin-bottom: 0.65rem;
  }
  .flight-card .rank { color: #60A5FA; font-weight: 700; font-size: 0.8rem; }
  .flight-card .airline { font-size: 1.05rem; font-weight: 600; color: #F8FAFC; }
  .flight-card .price { font-size: 1.2rem; font-weight: 700; color: #93C5FD; }
  .flight-card .meta { color: #94A3B8; font-size: 0.86rem; }
  .step {
    font-size: 0.75rem; padding: 0.32rem 0.6rem; border-radius: 999px;
    border: 1px solid #334155; background: #1E293B; color: #94A3B8;
  }
  .step.done { background: #172554; border-color: #1D4ED8; color: #BFDBFE; font-weight: 600; }
  .step.active { background: #2563EB; border-color: #2563EB; color: #fff; font-weight: 600; }
  .approval-box {
    border: 1px solid #334155; background: #111827; border-radius: 12px;
    padding: 0.85rem 1rem; margin: 0.5rem 0 0.75rem; color: #CBD5E1; font-size: 0.9rem;
  }
  div[data-testid="stMetricLabel"] p { color: #94A3B8 !important; }
  div[data-testid="stMetricValue"] { color: #F1F5F9 !important; font-size: 1.25rem; }
  [data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input {
    background-color: #111827 !important; color: #F1F5F9 !important;
    border-color: #334155 !important;
  }
"""


def inject_streamlit_css(dark: bool = False) -> None:
    theme = DARK_CSS if dark else LIGHT_CSS
    st.markdown(f"<style>{theme}</style>", unsafe_allow_html=True)


def render_header(demo_mode: bool) -> None:
    c1, c2 = st.columns([5, 1.2])
    with c1:
        mode_hint = " · Demo" if demo_mode else ""
        st.markdown(
            f'<p class="app-title">Flight Search AI Agent</p>'
            f'<p class="app-sub">Search, filter, approve, email{mode_hint}</p>',
            unsafe_allow_html=True,
        )
    with c2:
        st.toggle("Dark mode", key="dark_mode")


def workflow_phase(result: Optional[dict], awaiting: bool, email_done: bool) -> str:
    if not result:
        return "idle"
    status = result.get("status", "")
    if status == "missing_info":
        return "parse"
    if status == "parsed":
        return "memory"
    if status == "planned":
        return "plan"
    if status == "searched":
        return "search"
    if status == "no_flights":
        return "analyze"
    if status == "analyzed" or awaiting:
        return "approval" if awaiting else "analyze"
    if status == "awaiting_approval":
        return "approval"
    if email_done or status in {"approved", "completed"}:
        return "done" if status == "completed" else "email"
    if status == "rejected":
        return "approval"
    return "analyze"


def step_state(key: str, phase: str, status: str, awaiting: bool) -> str:
    order = [k for k, _ in WORKFLOW_STEPS]
    phase_to_idx = {
        "idle": -1,
        "parse": 0,
        "memory": 1,
        "plan": 2,
        "search": 3,
        "analyze": 4,
        "approval": 5,
        "email": 6,
        "done": 7,
    }
    idx = phase_to_idx.get(phase, -1)
    try:
        step_idx = order.index(key)
    except ValueError:
        return "wait"

    if status == "completed" or phase == "done":
        return "done"
    if key == "human_approval" and (status == "awaiting_approval" or awaiting):
        return "active"
    if step_idx < idx:
        return "done"
    if step_idx == idx:
        return "active"
    return "wait"


def render_workflow_stepper(result: Optional[dict], phase: str, awaiting: bool, email_done: bool) -> None:
    status = (result or {}).get("status", "")
    chips = []
    for key, label in WORKFLOW_STEPS:
        css = step_state(key, phase, status, awaiting)
        chips.append(f'<span class="step {css}">{label}</span>')
    st.markdown(f'<div class="stepper">{"".join(chips)}</div>', unsafe_allow_html=True)


def render_flight_cards(selected: List[dict]) -> None:
    if not selected:
        return
    for index, flight in enumerate(selected, start=1):
        st.markdown(
            f"""
<div class="flight-card">
  <div class="rank">#{index}</div>
  <div class="airline">{flight["airline"]} · {flight["flight_number"]}</div>
  <div class="price">{format_inr(flight["price"])}</div>
  <div class="meta">
    {flight["departure"]} → {flight["arrival"]} · {flight["duration"]} · {flight["stops"]} stop(s)
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )


def render_summary_metrics(result: dict) -> None:
    cols = st.columns(4)
    cols[0].metric("From", result.get("source") or "—")
    cols[1].metric("To", result.get("destination") or "—")
    budget = result.get("budget")
    cols[2].metric("Budget", format_inr(budget) if budget else "—")
    all_n = len(result.get("all_flights") or [])
    sel_n = len(result.get("selected_flights") or [])
    cols[3].metric("Matches", f"{sel_n} / {all_n}")
