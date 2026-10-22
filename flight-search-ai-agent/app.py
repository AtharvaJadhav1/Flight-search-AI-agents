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
    render_hero,
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
    initial_sidebar_state="expanded",
)


def init_session() -> None:
    defaults = {
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


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### About")
        st.caption(
            "Agentic AI prototype: LangGraph agents, mock flight data, "
            "optional OpenAI parsing, human-in-the-loop approval."
        )
        mode = "Demo Mode (no API key)" if is_demo_mode() else "LLM parsing enabled"
        st.info(f"**{mode}**")
        st.markdown("---")
        st.markdown("**Run locally**")
        st.code("streamlit run app.py", language="bash")
        st.code("python main.py", language="bash")
        st.markdown("---")
        st.caption(
            "Uses realistic **mock** flight data for reliable demos. "
            "A real API (e.g. Amadeus) can be added later."
        )


def main() -> None:
    init_session()
    inject_streamlit_css()
    render_sidebar()
    render_hero()

    left, right = st.columns([1.05, 1], gap="large")

    with left:
        st.markdown("#### New search")
        with st.form("search_form", clear_on_submit=False):
            user_request = st.text_area(
                "Flight request",
                height=110,
                label_visibility="collapsed",
                placeholder=(
                    "Find me the cheapest flight from Pune to Singapore under ₹30,000 "
                    "and email me the top 3 options."
                ),
            )
            email_address = st.text_input("Email", placeholder="you@example.com")
            submitted = st.form_submit_button("Search flights", type="primary", use_container_width=True)

        if submitted:
            if not user_request.strip():
                st.warning("Enter a flight search request.")
            elif not email_address.strip():
                st.warning("Enter your email address.")
            elif not validate_email(email_address):
                st.warning("Enter a valid email address.")
            else:
                details = extract_travel_details(user_request)
                mem = memory_for_streamlit()
                has_memory = mem.source and mem.destination and mem.budget
                if not has_memory and (
                    not details.get("source")
                    or not details.get("destination")
                    or not details.get("budget")
                ):
                    st.error("Include source, destination, and budget (e.g. under ₹30,000).")
                else:
                    with st.spinner("Running agent workflow…"):
                        run_search(user_request.strip(), email_address.strip())
                    st.rerun()

        with st.expander("Session memory (Unit III)", expanded=False):
            mem = memory_for_streamlit()
            display = mem.to_display_dict()
            if display.get("source"):
                st.json(display)
            else:
                st.caption("No memory yet. Complete a search to store route and budget.")
            if st.button("Clear memory", use_container_width=True):
                mem.clear()
                st.session_state.workflow_result = None
                st.session_state.awaiting_approval = False
                st.session_state.rejected = False
                st.session_state.email_done = False
                st.rerun()

    with right:
        result = st.session_state.workflow_result
        phase = workflow_phase(
            result,
            st.session_state.awaiting_approval,
            st.session_state.email_done,
        )

        st.markdown("#### Agent pipeline")
        render_workflow_stepper(
            result,
            phase,
            st.session_state.awaiting_approval,
            st.session_state.email_done,
        )

        if st.session_state.last_error:
            st.error(st.session_state.last_error)

        if not result:
            st.info("Submit a request to see workflow progress and flight options.")
        else:
            status = result.get("status", "")
            if status == "missing_info":
                st.error("Missing cities or budget in the request.")
            elif status == "no_flights":
                st.warning("No flights within budget. Try a higher budget or another route.")
            elif status == "error":
                st.error("Workflow failed. Check the message above.")

            if result.get("source") and status not in {"missing_info", "error"}:
                render_summary_metrics(result)

            if result.get("plan") and status in {"planned", "searched", "analyzed", "completed"}:
                with st.expander("Execution plan", expanded=False):
                    for i, step in enumerate(result["plan"], start=1):
                        st.markdown(f"{i}. {step}")

            if result.get("selected_flights"):
                render_flight_cards(result["selected_flights"])

            if st.session_state.awaiting_approval and result.get("selected_flights"):
                st.markdown(
                    '<div class="approval-box"><strong>Human-in-the-loop</strong><br/>'
                    "Approve to generate and simulate the email.</div>",
                    unsafe_allow_html=True,
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Approve & email", type="primary", use_container_width=True):
                        with st.spinner("Generating email…"):
                            resume_after_approval(True)
                        st.rerun()
                with c2:
                    if st.button("Reject", use_container_width=True):
                        resume_after_approval(False)
                        st.rerun()

            if st.session_state.rejected:
                st.error("Recommendation rejected. Adjust your request and search again.")

            if st.session_state.email_done and result.get("email_content"):
                st.success("Email generated · sent in Demo Mode (simulated)")
                st.text_area("Preview", value=result["email_content"], height=260, disabled=True)

    st.markdown(
        '<p class="footer-note">Flight Search AI Agent · Agentic AI Jury · Mock data for demonstration</p>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
