from __future__ import annotations

import re
import sys

from dotenv import load_dotenv

from agents import configure_unicode_output, extract_travel_details, is_demo_mode
from memory import ConversationMemory
from workflow import flight_agent_app, initial_state, run_config

configure_unicode_output()


def print_welcome() -> None:
    bar = "─" * 52
    print()
    print(bar)
    print("  ✈️  FLIGHT SEARCH AI AGENT")
    print("      Agentic AI · Terminal")
    print(bar)
    print()
    mode = "DEMO MODE (rule-based parsing)" if is_demo_mode() else "LLM + tools (OpenAI key)"
    print(f"  Mode     {mode}")
    print(f"  Web UI   streamlit run app.py")
    print()
    print("  Example request:")
    print("  Find cheapest Pune → Singapore under ₹30,000, top 3, email me.")
    print()
    print("  Follow-up: \"Show me only the cheapest one.\"")
    print("  Exit: quit / exit")
    print(bar)
    print()


def ask_email() -> str:
    print("Email")
    email = input("  › ").strip()
    if not email:
        email = "user@example.com"
        print("No email entered. Using user@example.com for the demo.")
    elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        print("That does not look like a valid email. Using it anyway for Demo Mode.")
    print()
    return email


def ask_request() -> str:
    print("Your request")
    request = input("  › ").strip()
    print()
    return request


def request_is_complete(user_request: str, memory: ConversationMemory) -> bool:
    details = extract_travel_details(user_request)
    source = details.get("source") or memory.source
    destination = details.get("destination") or memory.destination
    budget = details.get("budget") or memory.budget

    lower = user_request.lower()
    follow_up = any(
        phrase in lower
        for phrase in ("cheapest one", "only the cheapest", "same route", "previous search")
    )

    if follow_up and memory.source and memory.destination and memory.budget:
        return True

    if not source or not destination:
        print("❌ I could not find the source or destination city.")
        print("Please try again, for example: from Mumbai to Dubai")
        print()
        return False

    if not budget or budget <= 0:
        print("❌ Invalid budget. Please include a number, for example: under ₹30,000")
        print()
        return False

    return True


def memory_snapshot(memory: ConversationMemory) -> dict:
    return {
        "source": memory.source,
        "destination": memory.destination,
        "budget": memory.budget,
        "currency": memory.currency,
        "top_results": memory.top_results,
        "last_request": memory.last_user_request,
        "previous_selected_flights": memory.previous_selected_flights,
    }


def run_one_search(user_request: str, email_address: str, memory: ConversationMemory) -> dict:
    result = flight_agent_app.invoke(
        initial_state(
            user_request,
            email_address,
            ui_mode="terminal",
            memory_snapshot=memory_snapshot(memory),
        ),
        run_config("terminal-session"),
    )
    memory.update_from_state(result)
    return result


def print_result_footer(result: dict) -> None:
    print()
    print("=" * 49)
    status = result.get("status")
    if status == "completed":
        print("             ✅ TASK COMPLETED")
    elif status == "rejected":
        print("             ❌ RECOMMENDATION REJECTED")
        print("     Email was not generated.")
    elif status == "no_flights":
        print("             ⚠ TASK STOPPED")
        print("     No matching flights within budget.")
    elif status == "missing_info":
        print("             ⚠ TASK STOPPED")
        print("     Missing information in the request.")
    else:
        print("             ✅ TASK COMPLETED")
    print("=" * 49)
    print()


def main() -> None:
    load_dotenv()

    print_welcome()
    email_address = ask_email()
    memory = ConversationMemory()

    while True:
        user_request = ask_request()
        if not user_request:
            print("Please type a request.")
            print()
            continue
        if user_request.lower() in {"quit", "exit", "q"}:
            print("Goodbye.")
            break
        if not request_is_complete(user_request, memory):
            continue

        result = run_one_search(user_request, email_address, memory)
        print_result_footer(result)

        print("Search again? (y/n)")
        again = input("  › ").strip().lower()
        if again not in {"y", "yes"}:
            print("Goodbye.")
            break
        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled. Goodbye.")
        sys.exit(0)
