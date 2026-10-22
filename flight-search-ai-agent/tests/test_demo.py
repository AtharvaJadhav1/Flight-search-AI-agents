"""Lightweight tests for jury demo scenarios (no pytest required)."""

from __future__ import annotations

import os
import sys

# Project root on path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agents import extract_travel_details, is_demo_mode
from memory import ConversationMemory, apply_memory_to_state
from workflow import flight_agent_app, flight_agent_app_search, initial_state, run_config
from agents import generate_email, human_approval


def test_normal_request() -> None:
    os.environ.pop("OPENAI_API_KEY", None)
    assert is_demo_mode()
    req = (
        "Find me the cheapest flight from Pune to Singapore under ₹30,000 "
        "and email me the top 3 options."
    )
    result = flight_agent_app.invoke(
        initial_state(req, "demo@test.com", ui_mode="terminal", human_approved=True),
        run_config("test-normal"),
    )
    assert result["status"] == "completed"
    assert len(result["selected_flights"]) == 3
    assert result["selected_flights"][0]["price"] == 24500


def test_memory_follow_up() -> None:
    memory = ConversationMemory()
    memory.source = "Pune"
    memory.destination = "Singapore"
    memory.budget = 30000
    memory.top_results = 3

    state = {
        "user_request": "Show me only the cheapest one.",
        "source": None,
        "destination": None,
        "budget": None,
        "top_results": 3,
        "status": "missing_info",
    }
    merged = apply_memory_to_state(state, memory)
    assert merged["status"] == "parsed"
    assert merged["source"] == "Pune"
    assert merged["destination"] == "Singapore"
    assert merged["top_results"] == 1


def test_parser_demo_mode() -> None:
    os.environ.pop("OPENAI_API_KEY", None)
    details = extract_travel_details(
        "Find flights from Pune to Singapore under ₹30,000."
    )
    assert details["source"] == "Pune"
    assert details["destination"] == "Singapore"
    assert details["budget"] == 30000


def test_rejection_skips_email_content() -> None:
    req = (
        "Find me the cheapest flight from Pune to Singapore under ₹30,000 "
        "and email me the top 3 options."
    )
    result = flight_agent_app.invoke(
        initial_state(req, "demo@test.com", ui_mode="terminal", human_approved=False),
        run_config("test-reject"),
    )
    assert result["status"] == "rejected"
    assert not result.get("email_content")


def test_web_style_approval() -> None:
    req = (
        "Find me the cheapest flight from Pune to Singapore under ₹30,000 "
        "and email me the top 3 options."
    )
    state = flight_agent_app_search.invoke(
        initial_state(req, "web@test.com", ui_mode="streamlit"),
        run_config("test-web"),
    )
    assert state["status"] == "analyzed"
    state["human_approved"] = True
    state.update(human_approval(state))
    assert state["status"] == "approved"
    state.update(generate_email(state))
    assert state["status"] == "completed"
    assert state["email_content"]


def run_all() -> None:
    test_parser_demo_mode()
    test_memory_follow_up()
    test_normal_request()
    test_rejection_skips_email_content()
    test_web_style_approval()
    print("All demo tests passed.")


if __name__ == "__main__":
    run_all()
