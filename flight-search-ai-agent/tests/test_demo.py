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
from agents import build_email_draft, generate_email, human_approval, parse_with_rules
from tools import is_valid_email, parse_duration_minutes


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


def test_parser_budget_formats() -> None:
    assert parse_with_rules("Pune to Goa under 30k")["budget"] == 30000
    assert parse_with_rules("Pune to Goa below Rs. 25,000")["budget"] == 25000
    assert parse_with_rules("Pune to Goa budget 1.5 lakh")["budget"] == 150000
    assert parse_with_rules("Pune to Goa under ₹ 9,000")["budget"] == 9000


def test_parser_trims_filler_words() -> None:
    details = parse_with_rules("flights from Pune to Singapore for 2 adults under 30k")
    assert details["destination"] == "Singapore"


def test_parser_preferences() -> None:
    details = parse_with_rules("fastest nonstop from Mumbai to Dubai under 40000")
    assert details["max_stops"] == 0
    assert details["sort_by"] == "duration"


def test_nonstop_filter_and_trace() -> None:
    state = flight_agent_app_search.invoke(
        initial_state(
            "cheapest from Pune to Singapore under 40000 top 5",
            "a@b.co",
            ui_mode="streamlit",
            prefs={"max_stops": 0},
        ),
        run_config("test-nonstop"),
    )
    assert state["status"] == "analyzed"
    assert all(f["stops"] == 0 for f in state["selected_flights"])
    assert len(state["trace"]) >= 5


def test_fastest_sort() -> None:
    state = flight_agent_app_search.invoke(
        initial_state("fastest Pune to Singapore under 30000", "a@b.co", ui_mode="streamlit"),
        run_config("test-fast"),
    )
    minutes = [parse_duration_minutes(f["duration"]) for f in state["selected_flights"]]
    assert minutes == sorted(minutes)


def test_no_flights_under_budget() -> None:
    state = flight_agent_app_search.invoke(
        initial_state("Pune to Singapore under 5000", "a@b.co", ui_mode="streamlit"),
        run_config("test-none"),
    )
    assert state["status"] == "no_flights"


def test_garbage_does_not_replay_memory() -> None:
    memory = ConversationMemory()
    memory.source, memory.destination, memory.budget = "Pune", "Singapore", 30000
    state = {"user_request": "hello there", "status": "missing_info", "top_results": 3}
    assert apply_memory_to_state(state, memory)["status"] == "missing_info"


def test_partial_request_uses_memory() -> None:
    memory = ConversationMemory()
    memory.source, memory.destination, memory.budget = "Pune", "Singapore", 30000
    state = {"user_request": "under 20000", "budget": 20000, "status": "missing_info", "top_results": 3}
    merged = apply_memory_to_state(state, memory)
    assert merged["status"] == "parsed" and merged["budget"] == 20000 and merged["source"] == "Pune"


def test_email_override_and_delivery() -> None:
    os.environ.pop("SMTP_EMAIL", None)
    os.environ.pop("SMTP_PASSWORD", None)
    state = flight_agent_app_search.invoke(
        initial_state("Pune to Singapore under 30000", "a@b.co", ui_mode="streamlit"),
        run_config("test-override"),
    )
    assert "Hello" in build_email_draft(state)["body"]
    state["email_subject_override"] = "Custom subject"
    result = generate_email(state)
    assert result["email_content"].startswith("Subject: Custom subject")
    assert result["email_delivery"] == "demo"


def test_helpers() -> None:
    assert parse_duration_minutes("6h 30m") == 390
    assert is_valid_email("a@b.co") and not is_valid_email("nope")


def test_mock_data_is_route_aware() -> None:
    from data import get_mock_flights

    goa = get_mock_flights("Pune", "Goa")
    london = get_mock_flights("Delhi", "London")
    assert 10 <= len(goa) <= 20 and 10 <= len(london) <= 20
    assert get_mock_flights("Pune", "Goa") == goa  # stable between runs
    assert len({f["flight_number"] for f in goa}) == len(goa)
    assert min(f["price"] for f in goa) < 8000 < min(f["price"] for f in london)
    assert not {f["airline"] for f in goa} & {"Emirates", "Singapore Airlines"}
    assert all("baggage" in f and "refundable" in f for f in goa + london)
    assert get_mock_flights("Pune", "Narnia")  # unknown cities still work


def run_all() -> None:
    test_parser_demo_mode()
    test_parser_budget_formats()
    test_parser_trims_filler_words()
    test_parser_preferences()
    test_memory_follow_up()
    test_garbage_does_not_replay_memory()
    test_partial_request_uses_memory()
    test_normal_request()
    test_nonstop_filter_and_trace()
    test_fastest_sort()
    test_no_flights_under_budget()
    test_rejection_skips_email_content()
    test_web_style_approval()
    test_email_override_and_delivery()
    test_helpers()
    test_mock_data_is_route_aware()
    print("All demo tests passed.")


if __name__ == "__main__":
    run_all()
