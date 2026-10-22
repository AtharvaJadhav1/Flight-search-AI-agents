"""Shared UI styling for Streamlit and terminal."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from tools import format_inr

WORKFLOW_STEPS = [
    ("parse_request", "Parser"),
    ("apply_memory", "Memory"),
    ("create_plan", "Planning"),
    ("search_flights", "Search"),
    ("analyze_flights", "Analysis"),
    ("human_approval", "Approval"),
    ("generate_email", "Email"),
]


def inject_streamlit_css() -> None:
    st.markdown(
        """
<style>
  .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1100px; }
  header[data-testid="stHeader"] { background: transparent; }
  div[data-testid="stMetricValue"] { font-size: 1.35rem; font-weight: 600; }
  .hero {
    background: linear-gradient(135deg, #EEF2FF 0%, #F8FAFC 55%, #FFFFFF 100%);
    border: 1px solid #E2E8F0;
    border-radius: 16px;
    padding: 1.5rem 1.75rem 1.25rem;
    margin-bottom: 1rem;
  }
  .hero h1 { margin: 0; font-size: 1.85rem; color: #0F172A; font-weight: 700; }
  .hero p { margin: 0.35rem 0 0; color: #64748B; font-size: 0.95rem; }
  .badge {
    display: inline-block;
    background: #1D4ED8;
    color: #fff;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
    margin-bottom: 0.5rem;
  }
  .flight-card {
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 1rem 1.1rem;
    background: #FFFFFF;
    margin-bottom: 0.75rem;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  }
  .flight-card .rank { color: #1D4ED8; font-weight: 700; font-size: 0.85rem; }
  .flight-card .airline { font-size: 1.1rem; font-weight: 600; color: #0F172A; margin: 0.15rem 0; }
  .flight-card .price { font-size: 1.25rem; font-weight: 700; color: #1D4ED8; }
  .flight-card .meta { color: #64748B; font-size: 0.88rem; line-height: 1.45; }
  .stepper { display: flex; flex-wrap: wrap; gap: 0.35rem; margin: 0.5rem 0 0; }
  .step {
    font-size: 0.78rem;
    padding: 0.35rem 0.65rem;
    border-radius: 999px;
    border: 1px solid #E2E8F0;
    background: #F8FAFC;
    color: #64748B;
  }
  .step.done { background: #EEF2FF; border-color: #C7D2FE; color: #1D4ED8; font-weight: 600; }
  .step.active { background: #1D4ED8; border-color: #1D4ED8; color: #fff; font-weight: 600; }
  .step.wait { opacity: 0.85; }
  .approval-box {
    border: 1px solid #C7D2FE;
    background: #F8FAFF;
    border-radius: 12px;
    padding: 1rem 1.15rem;
    margin: 0.75rem 0;
  }
  .footer-note { color: #94A3B8; font-size: 0.8rem; text-align: center; margin-top: 2rem; }
</style>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
<div class="hero">
  <span class="badge">AGENTIC AI</span>
  <h1>Flight Search AI Agent</h1>
  <p>Natural language → plan → search → analyze → human approval → email</p>
</div>
        """,
        unsafe_allow_html=True,
    )


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
    if key == "human_approval" and status == "awaiting_approval" or awaiting:
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
    st.markdown(
        f'<div class="stepper">{"".join(chips)}</div>',
        unsafe_allow_html=True,
    )


def render_flight_cards(selected: List[dict]) -> None:
    if not selected:
        return
    st.markdown(f"#### Top {len(selected)} cheapest flights")
    medals = ["1", "2", "3"]
    for index, flight in enumerate(selected, start=1):
        rank = medals[index - 1] if index <= len(medals) else str(index)
        st.markdown(
            f"""
<div class="flight-card">
  <div class="rank">OPTION {rank}</div>
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
    cols[3].metric("Flights", f"{sel_n} selected / {all_n} found")
