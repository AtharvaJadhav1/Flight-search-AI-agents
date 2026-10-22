"""
Streamlit web interface for the Flight Search AI Agent.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime
from html import escape

import streamlit as st
from dotenv import load_dotenv

from agents import build_email_draft, generate_email, human_approval, is_demo_mode
from memory import SHOW_ALL_RESULTS, is_send_results_intent, memory_for_streamlit
from tools import format_inr, is_valid_email
from ui_theme import (
    inject_streamlit_css,
    notice,
    render_all_flights_table,
    render_empty_state,
    render_flight_cards,
    render_header,
    render_kpis,
    render_memory_panel,
    render_price_chart,
    render_stepper,
    render_timeline,
    section,
)
from workflow import flight_agent_app_search, initial_state, run_config

load_dotenv()

st.set_page_config(
    page_title="Flight Search AI Agent",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="auto",
)

EXAMPLES = [
    "Find flights from Pune to Singapore under ₹30,000",
    "Find flights from Mumbai to Dubai under ₹40,000",
    "Find flights from Delhi to Goa under ₹15,000",
]
MAX_HISTORY = 6


def init_session() -> None:
    defaults = {
        "dark_mode": False,
        "workflow_result": None,
        "awaiting_approval": False,
        "rejected": False,
        "email_done": False,
        "last_error": "",
        "form_error": "",
        "history": [],
        "thread_id": uuid.uuid4().hex,
        "run_counter": 0,
        "request_text": "",
        "email_address": "",
        "pref_nonstop": False,
        "pref_sort": "Cheapest",
        "draft_subject": "",
        "draft_body": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def set_request(text: str) -> None:
    st.session_state.request_text = text


def clear_memory() -> None:
    memory_for_streamlit().clear()
    st.session_state.history = []
    st.session_state.workflow_result = None
    st.session_state.awaiting_approval = False
    st.session_state.email_done = False
    st.session_state.rejected = False


def memory_snapshot_from_session() -> dict:
    mem = memory_for_streamlit()
    return {
        "source": mem.source,
        "destination": mem.destination,
        "budget": mem.budget,
        "currency": mem.currency,
        "top_results": mem.top_results,
        "last_request": mem.last_user_request,
        "previous_selected_flights": mem.previous_selected_flights,
        "sort_by": mem.sort_by,
        "max_stops": mem.max_stops,
    }


def should_request_approval(result: dict) -> bool:
    """Email approval only after the user refines to specific picks (not the full list)."""
    if result.get("status") != "analyzed":
        return False
    if not result.get("selected_flights"):
        return False
    top = result.get("top_results", SHOW_ALL_RESULTS)
    return top is not None and top > SHOW_ALL_RESULTS


def run_search(user_request: str, email_address: str, *, is_refinement: bool = False) -> None:
    st.session_state.last_error = ""
    st.session_state.rejected = False
    st.session_state.email_done = False
    st.session_state.awaiting_approval = False
    st.session_state.run_counter += 1

    mem = memory_for_streamlit()
    if is_refinement:
        mem.refinement_count += 1

    if is_send_results_intent(user_request):
        prior = st.session_state.workflow_result
        if prior and prior.get("selected_flights"):
            st.session_state.awaiting_approval = True
            draft = build_email_draft(prior)
            st.session_state.draft_subject = draft["subject"]
            st.session_state.draft_body = draft["body"]
            return
        if not mem.has_search_context():
            st.session_state.workflow_result = {
                "status": "missing_info",
                "memory_note": (
                    "No previous flight search in this session. "
                    "Start with a route and budget first."
                ),
            }
            return

    sort_pref = "duration" if st.session_state.pref_sort == "Fastest" else "price"
    state = initial_state(
        user_request,
        email_address,
        ui_mode="streamlit",
        human_approved=None,
        memory_snapshot=memory_snapshot_from_session(),
        prefs={
            "max_stops": 0 if st.session_state.pref_nonstop else mem.max_stops,
            "sort_by": sort_pref,
        },
    )
    config = run_config(f"{st.session_state.thread_id}-{st.session_state.run_counter}")

    try:
        result = flight_agent_app_search.invoke(state, config)
    except Exception as error:
        st.session_state.last_error = str(error)
        st.session_state.workflow_result = {"status": "error"}
        return

    st.session_state.workflow_result = result
    mem.update_from_state(result)

    if should_request_approval(result):
        st.session_state.awaiting_approval = True
        draft = build_email_draft(result)
        st.session_state.draft_subject = draft["subject"]
        st.session_state.draft_body = draft["body"]

    if not is_refinement and result.get("status") == "analyzed":
        best = (result.get("selected_flights") or [{}])[0]
        price = best.get("price")
        history = st.session_state.history
        history.insert(
            0,
            {
                "request": user_request,
                "label": f'{result["source"]} → {result["destination"]} · {format_inr(price) if price else "—"}',
                "time": datetime.now().strftime("%H:%M"),
            },
        )
        del history[MAX_HISTORY:]


def resume_after_approval(approved: bool) -> None:
    base = dict(st.session_state.workflow_result or {})
    base["ui_mode"] = "streamlit"
    base["human_approved"] = approved
    base["email_subject_override"] = st.session_state.draft_subject.strip()
    base["email_body_override"] = st.session_state.draft_body.strip()

    try:
        base.update(human_approval(base))
        if approved and base.get("status") == "approved":
            base.update(generate_email(base))
    except Exception as error:
        st.session_state.last_error = str(error)
        return

    st.session_state.workflow_result = base
    st.session_state.awaiting_approval = False
    if base.get("status") == "rejected":
        st.session_state.rejected = True
        return
    memory_for_streamlit().update_from_state(base)
    st.session_state.email_done = base.get("status") == "completed"


def flights_csv(flights: list) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Airline", "Flight", "Departure", "Arrival", "Duration", "Stops", "Price (INR)"])
    for f in flights:
        writer.writerow(
            [f["airline"], f["flight_number"], f["departure"], f["arrival"], f["duration"], f["stops"], f["price"]]
        )
    return buffer.getvalue()


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### ✈ Flight Agent")
        st.toggle("Dark mode", key="dark_mode")

        section("Search preferences")
        st.checkbox("Nonstop flights only", key="pref_nonstop")
        st.radio("Sort by", ["Cheapest", "Fastest"], key="pref_sort", horizontal=True)

        section("Session memory")
        mem = memory_for_streamlit()
        render_memory_panel(mem.to_display_dict())
        st.caption("Refine prompts reuse route, budget, and filters from the last search.")
        st.button("Clear session", on_click=clear_memory, use_container_width=True)

        if st.session_state.history:
            section("Recent searches")
            for index, item in enumerate(st.session_state.history):
                st.button(
                    f'{item["label"]}',
                    key=f"hist_{index}",
                    help=f'{item["time"]} — {item["request"]}',
                    on_click=set_request,
                    args=(item["request"],),
                    use_container_width=True,
                )


def render_search_card() -> None:
    with st.container(border=True):
        st.markdown("**1. Search flights**")
        st.text_area(
            "What are you looking for?",
            key="request_text",
            height=92,
            placeholder="e.g. Find flights from Pune to Singapore under ₹30,000",
        )
        col_email, col_btn = st.columns([3, 1], vertical_alignment="bottom")
        with col_email:
            st.text_input("Send results to", key="email_address", placeholder="you@example.com")
        with col_btn:
            submitted = st.button("Search flights", type="primary", use_container_width=True)

        st.caption("Try an example:")
        chip_cols = st.columns(len(EXAMPLES))
        for index, (col, example) in enumerate(zip(chip_cols, EXAMPLES)):
            col.button(example, key=f"chip_{index}", on_click=set_request, args=(example,), use_container_width=True)

    if submitted:
        request = st.session_state.request_text.strip()
        email = st.session_state.email_address.strip()
        if not request:
            st.session_state.form_error = "Enter a request, or pick one of the examples."
        elif not is_valid_email(email):
            st.session_state.form_error = "Enter a valid email address (e.g. you@example.com)."
        else:
            st.session_state.form_error = ""
            with st.spinner("Searching…"):
                run_search(request, email, is_refinement=False)
            st.rerun()
    if st.session_state.form_error:
        notice("warn", st.session_state.form_error)


def render_refine_prompt() -> None:
    mem = memory_for_streamlit()
    if not mem.has_search_context():
        return
    with st.container(border=True):
        st.markdown("**2. Refine results** (uses session memory)")
        st.caption(
            f"Context: **{mem.source} → {mem.destination}** · {format_inr(mem.budget or 0)}"
        )
        with st.form("refine_results_form", clear_on_submit=True):
            col_text, col_btn = st.columns([5, 1], vertical_alignment="bottom")
            with col_text:
                refine_query = st.text_input(
                    "Refine",
                    label_visibility="collapsed",
                    placeholder='e.g. "Give me the cheapest flight" or "Show top 3 fastest"',
                )
            with col_btn:
                submitted = st.form_submit_button("Apply", use_container_width=True)
    if submitted:
        text = (refine_query or "").strip()
        email = st.session_state.email_address.strip()
        if not text:
            st.session_state.form_error = "Type a refinement, such as: give me the cheapest flight."
            st.rerun()
        if not is_valid_email(email):
            st.session_state.form_error = "Enter your email in step 1 first."
            st.rerun()
        st.session_state.form_error = ""
        with st.spinner("Refining…"):
            run_search(text, email, is_refinement=True)
        st.rerun()


def render_approval(result: dict) -> None:
    section("Human approval")
    notice(
        "info",
        "<b>Review before sending.</b> The agent drafted this email from the selected flights. "
        "Edit it if you like, then approve to send, or reject to start over.",
    )
    st.text_input("Subject", key="draft_subject")
    st.text_area("Message", key="draft_body", height=240)
    c1, c2 = st.columns(2)
    if c1.button("Approve & send", type="primary", use_container_width=True):
        with st.spinner("Sending…"):
            resume_after_approval(True)
        st.rerun()
    if c2.button("Reject", use_container_width=True):
        resume_after_approval(False)
        st.rerun()


def render_results(result: dict) -> None:
    status = result.get("status", "")
    if status == "missing_info":
        missing = result.get("memory_note") or ""
        notice(
            "bad",
            "<b>I couldn't understand the request.</b> Please include a source city, a destination city "
            "and a budget, e.g. <i>“Pune to Singapore under ₹30,000”</i>."
            + (f"<br>{missing}" if missing and "Could not resolve" not in missing else ""),
        )
    elif status == "no_flights":
        notice(
            "warn",
            f'<b>No flights matched.</b> Nothing from {result.get("source")} to {result.get("destination")} '
            f'fits {format_inr(result.get("budget") or 0)}'
            + (" with nonstop only" if result.get("max_stops") == 0 else "")
            + ". Try a higher budget or allow connecting flights.",
        )
    elif status == "error":
        notice("bad", "<b>Something went wrong</b> while running the agents. Please try again.")

    if result.get("source") and status not in {"missing_info", "error"}:
        render_kpis(result)

    selected = result.get("selected_flights") or []
    show_all = result.get("top_results", SHOW_ALL_RESULTS) == SHOW_ALL_RESULTS

    if selected or result.get("all_flights"):
        if show_all:
            notice(
                "info",
                f"<b>{len(selected)} flights</b> within your budget. "
                "Use <b>Refine results</b> above to narrow down (e.g. cheapest only).",
            )
            tabs = st.tabs(["All flights in budget", "Price chart", "Agent activity"])
            with tabs[0]:
                render_all_flights_table(result)
                st.download_button(
                    "Download all (CSV)",
                    flights_csv(result.get("filtered_flights") or selected),
                    file_name="flights_in_budget.csv",
                    mime="text/csv",
                )
            with tabs[1]:
                render_price_chart(result)
            with tabs[2]:
                render_timeline(result.get("trace") or [])
        else:
            tabs = st.tabs(["Top picks", "All flights", "Price chart", "Agent activity"])
            with tabs[0]:
                render_flight_cards(selected, result.get("budget") or 0)
                st.download_button(
                    "Download picks (CSV)",
                    flights_csv(selected),
                    file_name="flight_picks.csv",
                    mime="text/csv",
                )
            with tabs[1]:
                render_all_flights_table(result)
            with tabs[2]:
                render_price_chart(result)
            with tabs[3]:
                render_timeline(result.get("trace") or [])
                with st.expander("Execution plan"):
                    for index, step in enumerate(result.get("plan") or [], start=1):
                        st.markdown(f"{index}. {step}")
    elif result.get("trace"):
        with st.expander("Agent activity"):
            render_timeline(result["trace"])

    if st.session_state.awaiting_approval and selected:
        render_approval(result)

    if st.session_state.rejected:
        notice("warn", "<b>Recommendation rejected.</b> No email was sent. Adjust your request and search again.")

    if st.session_state.email_done and result.get("email_content"):
        delivery = result.get("email_delivery")
        if delivery == "sent":
            notice("good", f'<b>Email sent</b> to {result.get("email_address")}.')
        else:
            notice(
                "info",
                "<b>Demo send.</b> No SMTP credentials are configured, so the email was simulated, not delivered.",
            )
        with st.expander("View sent email", expanded=True):
            st.markdown(f'<div class="mail">{escape(result["email_content"])}</div>', unsafe_allow_html=True)
        st.download_button(
            "Download email (.txt)",
            result["email_content"],
            file_name="flight_email.txt",
            mime="text/plain",
        )


def main() -> None:
    init_session()
    inject_streamlit_css(bool(st.session_state.dark_mode))
    render_sidebar()
    render_header(is_demo_mode())
    render_search_card()

    result = st.session_state.workflow_result
    if result and result.get("status") not in {None, "missing_info", "error"}:
        render_refine_prompt()

    section("Progress")
    render_stepper((result or {}).get("status", ""), st.session_state.awaiting_approval)

    if st.session_state.last_error:
        notice("bad", f'<b>Error:</b> {st.session_state.last_error}')

    if not result:
        render_empty_state()
    else:
        render_results(result)


if __name__ == "__main__":
    main()
