"""Lightweight tests for jury demo scenarios (no pytest required)."""

from __future__ import annotations

import os
import sys

# Project root on path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agents import extract_travel_details, is_demo_mode
from memory import ConversationMemory, apply_memory_to_state, is_follow_up_message
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


def test_cheapest_three_follow_up() -> None:
    memory = ConversationMemory()
    memory.source, memory.destination, memory.budget = "Pune", "Singapore", 30000
    state = {
        "user_request": "Show me only the cheapest 3.",
        "status": "missing_info",
        "top_results": 3,
    }
    merged = apply_memory_to_state(state, memory)
    assert merged["status"] == "parsed"
    assert merged["source"] == "Pune"
    assert merged["budget"] == 30000
    assert merged["top_results"] == 3


def test_fastest_follow_up() -> None:
    memory = ConversationMemory()
    memory.source, memory.destination, memory.budget = "Pune", "Singapore", 30000
    state = {"user_request": "Now show me the fastest one.", "status": "missing_info", "top_results": 3}
    merged = apply_memory_to_state(state, memory)
    assert merged["sort_by"] == "duration"
    assert merged["top_results"] == 1


def test_nonstop_follow_up() -> None:
    memory = ConversationMemory()
    memory.source, memory.destination, memory.budget = "Pune", "Singapore", 30000
    state = {"user_request": "Only show nonstop flights.", "status": "missing_info", "top_results": 3}
    merged = apply_memory_to_state(state, memory)
    assert merged["max_stops"] == 0


def test_new_search_replaces_context() -> None:
    memory = ConversationMemory()
    memory.source, memory.destination, memory.budget = "Pune", "Singapore", 30000
    state = {
        "user_request": "Now find flights from Delhi to Goa under ₹15,000.",
        "source": "Delhi",
        "destination": "Goa",
        "budget": 15000,
        "status": "parsed",
        "top_results": 3,
    }
    merged = apply_memory_to_state(state, memory)
    assert merged["source"] == "Delhi"
    assert merged["destination"] == "Goa"
    assert merged["budget"] == 15000


def test_give_me_cheapest_follow_up() -> None:
    memory = ConversationMemory()
    memory.source, memory.destination, memory.budget = "Pune", "Singapore", 30000
    state = {"user_request": "Give me the cheapest flight", "status": "missing_info", "top_results": 0}
    merged = apply_memory_to_state(state, memory)
    assert merged["status"] == "parsed"
    assert merged["top_results"] == 1
    assert merged["sort_by"] == "price"


def test_initial_search_shows_all_in_budget() -> None:
    state = flight_agent_app_search.invoke(
        initial_state("Find flights from Pune to Singapore under ₹30,000.", "a@b.co", ui_mode="streamlit"),
        run_config("test-all"),
    )
    assert state["top_results"] == 0
    assert len(state["selected_flights"]) == 6


def test_no_memory_helpful_error() -> None:
    memory = ConversationMemory()
    state = {"user_request": "Show me the cheapest one.", "status": "missing_info", "top_results": 3}
    merged = apply_memory_to_state(state, memory)
    assert merged["status"] == "missing_info"
    assert "previous flight search" in merged["memory_note"].lower()


def test_multi_turn_workflow() -> None:
    os.environ.pop("OPENAI_API_KEY", None)
    mem = ConversationMemory()
    req1 = "Find flights from Pune to Singapore under ₹30,000."
    s1 = flight_agent_app_search.invoke(
        initial_state(req1, "a@b.co", ui_mode="streamlit", memory_snapshot={}),
        run_config("test-mt-1"),
    )
    mem.update_from_state(s1)
    assert s1["status"] == "analyzed" and len(s1["selected_flights"]) == 6

    snap = {
        "source": mem.source,
        "destination": mem.destination,
        "budget": mem.budget,
        "top_results": mem.top_results,
        "last_request": req1,
        "previous_selected_flights": s1["selected_flights"],
        "sort_by": mem.sort_by,
        "max_stops": mem.max_stops,
    }
    s2 = flight_agent_app_search.invoke(
        initial_state("Give me the cheapest 3.", "a@b.co", ui_mode="streamlit", memory_snapshot=snap),
        run_config("test-mt-2"),
    )
    assert s2["source"] == "Pune" and s2["budget"] == 30000
    assert len(s2["selected_flights"]) == 3

    snap2 = dict(snap)
    mem.update_from_state(s2)
    snap2.update(
        {
            "source": mem.source,
            "destination": mem.destination,
            "budget": mem.budget,
            "sort_by": mem.sort_by,
            "max_stops": mem.max_stops,
        }
    )
    s3 = flight_agent_app_search.invoke(
        initial_state("Now show me the fastest one.", "a@b.co", ui_mode="streamlit", memory_snapshot=snap2),
        run_config("test-mt-3"),
    )
    assert s3["sort_by"] == "duration"
    assert len(s3["selected_flights"]) == 1


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
    test_initial_search_shows_all_in_budget()
    test_give_me_cheapest_follow_up()
    test_cheapest_three_follow_up()
    test_fastest_follow_up()
    test_nonstop_follow_up()
    test_new_search_replaces_context()
    test_no_memory_helpful_error()
    test_multi_turn_workflow()
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
