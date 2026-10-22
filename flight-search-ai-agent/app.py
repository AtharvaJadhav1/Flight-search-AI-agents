"""
Streamlit web interface for the Flight Search AI Agent.
"""

from __future__ import annotations

import re

import streamlit as st
from dotenv import load_dotenv

from agents import extract_travel_details, generate_email, human_approval, is_demo_mode
from memory import memory_for_streamlit
from ui_theme import (
    inject_streamlit_css,
    render_flight_cards,
    render_header,
    render_summary_metrics,
    render_workflow_stepper,
    workflow_phase,
)
from workflow import flight_agent_app_search, initial_state, run_config

load_dotenv()

st.set_page_config(
    page_title="Flight Search AI Agent",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def init_session() -> None:
    defaults = {
        "dark_mode": False,
        "workflow_result": None,
        "awaiting_approval": False,
        "rejected": False,
        "email_done": False,
        "last_error": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


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
    }


def run_search(user_request: str, email_address: str) -> None:
    st.session_state.last_error = ""
    st.session_state.rejected = False
    st.session_state.email_done = False
    st.session_state.awaiting_approval = False

    state = initial_state(
        user_request,
        email_address,
        ui_mode="streamlit",
        human_approved=None,
        memory_snapshot=memory_snapshot_from_session(),
    )

    try:
        result = flight_agent_app_search.invoke(state, run_config("streamlit-search"))
    except Exception as error:
        st.session_state.last_error = str(error)
        st.session_state.workflow_result = {"status": "error"}
        return

    st.session_state.workflow_result = result
    memory_for_streamlit().update_from_state(result)

    if result.get("status") == "analyzed" and result.get("selected_flights"):
        st.session_state.awaiting_approval = True


def resume_after_approval(approved: bool) -> None:
    base = dict(st.session_state.workflow_result or {})
    base["ui_mode"] = "streamlit"
    base["human_approved"] = approved

    try:
        base.update(human_approval(base))
    except Exception as error:
        st.session_state.last_error = str(error)
        return

    if not approved or base.get("status") == "rejected":
        st.session_state.rejected = True
        st.session_state.awaiting_approval = False
        base["status"] = "rejected"
        st.session_state.workflow_result = base
        return

    try:
        base.update(generate_email(base))
    except Exception as error:
        st.session_state.last_error = str(error)
        return

    st.session_state.workflow_result = base
    memory_for_streamlit().update_from_state(base)
    st.session_state.awaiting_approval = False
    st.session_state.email_done = base.get("status") == "completed"


def main() -> None:
    init_session()
    dark = bool(st.session_state.dark_mode)
    inject_streamlit_css(dark)
    render_header(is_demo_mode())

    left, right = st.columns([1, 1], gap="large")

    with left:
        with st.form("search_form", clear_on_submit=False):
            user_request = st.text_area(
                "Request",
                height=100,
                placeholder=(
                    "Cheapest flight Pune to Singapore under ₹30,000, email top 3."
                ),
            )
            email_address = st.text_input("Email", placeholder="you@example.com")
            submitted = st.form_submit_button("Search", type="primary", use_container_width=True)

        if submitted:
            if not user_request.strip():
                st.warning("Enter a request.")
            elif not email_address.strip() or not validate_email(email_address):
                st.warning("Enter a valid email.")
            else:
                details = extract_travel_details(user_request)
                mem = memory_for_streamlit()
                has_memory = mem.source and mem.destination and mem.budget
                if not has_memory and (
                    not details.get("source")
                    or not details.get("destination")
                    or not details.get("budget")
                ):
                    st.error("Include cities and budget (e.g. under ₹30,000).")
                else:
                    with st.spinner("Working…"):
                        run_search(user_request.strip(), email_address.strip())
                    st.rerun()

    with right:
        result = st.session_state.workflow_result
        phase = workflow_phase(
            result,
            st.session_state.awaiting_approval,
            st.session_state.email_done,
        )

        render_workflow_stepper(
            result,
            phase,
            st.session_state.awaiting_approval,
            st.session_state.email_done,
        )

        if st.session_state.last_error:
            st.error(st.session_state.last_error)

        if not result:
            st.caption("Results appear here after you search.")
        else:
            status = result.get("status", "")
            if status == "missing_info":
                st.error("Missing cities or budget.")
            elif status == "no_flights":
                st.warning("No flights in budget.")
            elif status == "error":
                st.error("Something went wrong.")

            if result.get("source") and status not in {"missing_info", "error"}:
                render_summary_metrics(result)

            if result.get("selected_flights"):
                render_flight_cards(result["selected_flights"])

            if st.session_state.awaiting_approval and result.get("selected_flights"):
                st.markdown(
                    '<div class="approval-box">Approve to send the email summary.</div>',
                    unsafe_allow_html=True,
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Approve", type="primary", use_container_width=True):
                        with st.spinner("Sending…"):
                            resume_after_approval(True)
                        st.rerun()
                with c2:
                    if st.button("Reject", use_container_width=True):
                        resume_after_approval(False)
                        st.rerun()

            if st.session_state.rejected:
                st.error("Rejected. Change your request and search again.")

            if st.session_state.email_done and result.get("email_content"):
                st.success("Email ready (demo send)")
                st.text_area("Email", value=result["email_content"], height=220, disabled=True)


if __name__ == "__main__":
    main()
