"""
Streamlit web interface for the Flight Search AI Agent.
"""

from __future__ import annotations

import re

import streamlit as st
from dotenv import load_dotenv

from agents import (
    extract_travel_details,
    generate_email,
    human_approval,
    is_demo_mode,
)
from memory import memory_for_streamlit
from tools import format_inr
from workflow import flight_agent_app_search, initial_state, run_config

load_dotenv()

st.set_page_config(
    page_title="Flight Search AI Agent",
    page_icon="✈️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

MEDALS = ["🥇", "🥈", "🥉"]
WORKFLOW_STEPS = [
    ("parse_request", "Request Parser"),
    ("apply_memory", "Short-Term Memory"),
    ("create_plan", "Planning Agent"),
    ("search_flights", "Flight Search Agent"),
    ("analyze_flights", "Flight Analysis Agent"),
    ("human_approval", "Human Approval"),
    ("generate_email", "Email Generation"),
]


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


def render_workflow_progress(result: dict | None, phase: str) -> None:
    """Show agent pipeline with checkmarks based on current phase."""
    st.subheader("Agent Workflow")
    status = (result or {}).get("status", "")
    step_done = {
        "parse_request": phase in {"memory", "plan", "search", "analyze", "approval", "email", "done"},
        "apply_memory": phase in {"plan", "search", "analyze", "approval", "email", "done"},
        "create_plan": phase in {"search", "analyze", "approval", "email", "done"},
        "search_flights": phase in {"analyze", "approval", "email", "done"},
        "analyze_flights": phase in {"approval", "email", "done"} or status in {
            "awaiting_approval",
            "approved",
            "rejected",
            "completed",
        },
        "human_approval": phase in {"email", "done"}
        or status in {"awaiting_approval", "approved", "rejected", "completed"},
        "generate_email": phase == "done" or status == "completed",
    }

    if status == "awaiting_approval":
        step_done["human_approval"] = False

    lines = []
    for key, label in WORKFLOW_STEPS:
        if key == "human_approval" and status == "awaiting_approval":
            icon = "⏳"
        elif step_done.get(key):
            icon = "✓"
        else:
            icon = "○"
        lines.append(f"{icon} {label}")

    st.markdown("  \n".join(lines).replace("○", "&nbsp;&nbsp;○"))


def render_flights(selected: list) -> None:
    if not selected:
        return
    st.subheader(f"TOP {len(selected)} CHEAPEST FLIGHTS")
    for index, flight in enumerate(selected, start=1):
        medal = MEDALS[index - 1] if index <= len(MEDALS) else "✈️"
        st.markdown(
            f"""
**{medal} {flight['airline']}**  
Flight: {flight['flight_number']}  
Price: {format_inr(flight['price'])}  
Duration: {flight['duration']}  
Departure: {flight['departure']} → Arrival: {flight['arrival']}  
Stops: {flight['stops']}
"""
        )
        st.divider()


def run_search(user_request: str, email_address: str) -> None:
    st.session_state.last_error = ""
    st.session_state.rejected = False
    st.session_state.email_done = False
    st.session_state.awaiting_approval = False

    snapshot = memory_snapshot_from_session()
    state = initial_state(
        user_request,
        email_address,
        ui_mode="streamlit",
        human_approved=None,
        memory_snapshot=snapshot,
    )

    config = run_config("streamlit-search")
    try:
        result = flight_agent_app_search.invoke(state, config)
    except Exception as error:
        st.session_state.last_error = str(error)
        st.session_state.workflow_result = {"status": "error"}
        return

    st.session_state.workflow_result = result
    mem = memory_for_streamlit()
    mem.update_from_state(result)

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
    mem = memory_for_streamlit()
    mem.update_from_state(base)
    st.session_state.awaiting_approval = False
    st.session_state.email_done = base.get("status") == "completed"


def main() -> None:
    init_session()

    st.title("✈️ Flight Search AI Agent")
    st.caption("Agentic AI Mini Project")

    mode_label = "Demo / Offline (rule-based parsing)" if is_demo_mode() else "LLM + tools (OpenAI)"
    st.info(f"**Mode:** {mode_label}")

    with st.form("search_form", clear_on_submit=False):
        user_request = st.text_area(
            "Flight request (natural language)",
            height=100,
            placeholder=(
                "Find me the cheapest flight from Pune to Singapore under ₹30,000 "
                "and email me the top 3 options."
            ),
        )
        email_address = st.text_input("Email address", placeholder="you@example.com")
        submitted = st.form_submit_button("🔍 Search Flights", type="primary")

    if submitted:
        if not user_request.strip():
            st.warning("Please enter a flight search request.")
        elif not email_address.strip():
            st.warning("Please enter an email address.")
        elif not validate_email(email_address):
            st.warning("That email does not look valid. Please check and try again.")
        else:
            details = extract_travel_details(user_request)
            mem = memory_for_streamlit()
            has_memory = mem.source and mem.destination and mem.budget
            if not has_memory and (
                not details.get("source")
                or not details.get("destination")
                or not details.get("budget")
            ):
                st.error(
                    "Could not find source, destination, and budget. "
                    "Example: from Pune to Singapore under ₹30,000"
                )
            else:
                with st.spinner("Running agent workflow..."):
                    run_search(user_request.strip(), email_address.strip())

    result = st.session_state.workflow_result
    phase = "idle"
    if result:
        status = result.get("status", "")
        if status == "missing_info":
            phase = "parse"
        elif status in {"parsed"}:
            phase = "memory"
        elif status == "planned":
            phase = "plan"
        elif status == "searched":
            phase = "search"
        elif status == "analyzed":
            phase = "analyze"
        elif status == "awaiting_approval":
            phase = "approval"
        elif status == "approved" or st.session_state.email_done:
            phase = "email"
        elif status == "completed":
            phase = "done"
        elif status == "no_flights":
            phase = "analyze"
        else:
            phase = "analyze"

    if result:
        render_workflow_progress(result, phase)

    if st.session_state.last_error:
        st.error(f"Something went wrong: {st.session_state.last_error}")

    if result:
        status = result.get("status", "")
        if status == "missing_info":
            st.error("Missing information in the request. Try adding cities and a budget.")
        elif status == "no_flights":
            st.warning("No flights found within your budget. Try increasing the budget.")
        elif result.get("selected_flights"):
            render_flights(result["selected_flights"])

    if st.session_state.awaiting_approval and result and result.get("selected_flights"):
        st.subheader("🤖 Agent Recommendation")
        st.write("Do you want to proceed with these recommendations?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Approve & Generate Email", type="primary"):
                with st.spinner("Generating email..."):
                    resume_after_approval(True)
                st.rerun()
        with col2:
            if st.button("❌ Reject"):
                resume_after_approval(False)
                st.rerun()

    if st.session_state.rejected:
        st.error(
            "❌ Recommendation rejected.\n\nYou can modify your request and perform another search."
        )

    if st.session_state.email_done and result and result.get("email_content"):
        st.subheader("Generated Email")
        st.success("✓ Human approval received\n\n✓ Email generated successfully")
        st.text_area("Email preview", value=result["email_content"], height=280)

    st.subheader("Conversation Memory (Unit III)")
    mem = memory_for_streamlit()
    display = mem.to_display_dict()
    if display["source"]:
        st.json(display)
    else:
        st.caption("No session memory yet. Run a search to store source, destination, and budget.")

    if st.button("Clear session memory"):
        mem.clear()
        st.session_state.workflow_result = None
        st.session_state.awaiting_approval = False
        st.session_state.rejected = False
        st.session_state.email_done = False
        st.rerun()


if __name__ == "__main__":
    main()
