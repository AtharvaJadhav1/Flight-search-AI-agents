"""
Agent logic: parsing, planning, searching, analyzing, and emailing.

Each function is one node in the LangGraph workflow. Agents reason or decide;
tools (in tools.py) perform the actual actions.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

from data import KNOWN_CITIES
from memory import ConversationMemory, apply_memory_to_state
from tools import flight_search_tool, format_inr, send_email_tool


def configure_unicode_output() -> None:
    """Make emojis print correctly on Windows terminals."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass


configure_unicode_output()


LINE = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
MEDALS = ["🥇", "🥈", "🥉"]


def is_demo_mode() -> bool:
    """Demo Mode is ON when there is no OpenAI API key."""
    return not os.getenv("OPENAI_API_KEY", "").strip()


def banner(title: str) -> None:
    print()
    print("=" * 49)
    print(title)
    print("=" * 49)
    print()


def _clean_city(name: str) -> str:
    name = name.strip(" .,!?;:'\"")
    name = re.sub(r"\s+", " ", name)
    return name.title()


def parse_with_rules(user_request: str) -> Dict[str, Any]:
    """
    Rule-based parser used when no OpenAI key is available.

    It looks for:
    - from <city> to <city>
    - a budget number near words like under / below / budget
    - top N results
    """
    text = user_request.strip()
    lower = text.lower()

    source = None
    destination = None

    # Prefer an explicit "from X to Y" pattern.
    from_to = re.search(
        r"from\s+([a-zA-Z][a-zA-Z\s]{1,40}?)\s+to\s+([a-zA-Z][a-zA-Z\s]{1,40}?)(?:\s+under|\s+below|\s+within|\s+and|\s+with|\s*$|[.,!])",
        text,
        flags=re.IGNORECASE,
    )
    if from_to:
        source = _clean_city(from_to.group(1))
        destination = _clean_city(from_to.group(2))

    # Fallback: match known city names in order of appearance.
    if not source or not destination:
        found = []
        search_area = lower
        for city in sorted(KNOWN_CITIES, key=len, reverse=True):
            pattern = r"\b" + re.escape(city.lower()) + r"\b"
            match = re.search(pattern, search_area)
            if match:
                found.append((match.start(), city))
                # Hide this match so "New Delhi" is not also counted as "Delhi".
                search_area = (
                    search_area[: match.start()]
                    + (" " * (match.end() - match.start()))
                    + search_area[match.end() :]
                )
        found.sort(key=lambda item: item[0])
        unique = []
        for _, city in found:
            if city.title() not in unique:
                unique.append(city.title())
        if len(unique) >= 2:
            source = source or unique[0]
            destination = destination or unique[1]

    budget = None
    currency = "INR"
    budget_match = re.search(
        r"(?:under|below|within|less than|budget of|upto|up to)\s*₹?\s*([\d,]+)",
        lower,
    )
    if not budget_match:
        budget_match = re.search(r"₹\s*([\d,]+)", text)
    if not budget_match:
        budget_match = re.search(r"(?:rs\.?|inr)\s*([\d,]+)", lower)
    if budget_match:
        try:
            budget = int(budget_match.group(1).replace(",", ""))
        except ValueError:
            budget = None

    top_results = 3
    top_match = re.search(r"top\s+(\d+)", lower)
    if top_match:
        top_results = max(1, int(top_match.group(1)))
    else:
        show_match = re.search(r"(?:show|email|send)\s+(?:me\s+)?(\d+)", lower)
        if show_match:
            top_results = max(1, int(show_match.group(1)))

    return {
        "source": source,
        "destination": destination,
        "budget": budget,
        "currency": currency,
        "top_results": top_results,
    }


def parse_with_llm(user_request: str) -> Optional[Dict[str, Any]]:
    """Use OpenAI to extract travel details. Returns None if anything fails."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        prompt = (
            "Extract flight search details from the user request. "
            "Return ONLY valid JSON with keys: source, destination, budget, "
            "currency, top_results. budget must be an integer. "
            "currency should be INR unless another currency is clearly mentioned. "
            "top_results should default to 3 if not mentioned.\n\n"
            f"User request: {user_request}"
        )
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "You extract structured travel details. Reply with JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or ""
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?", "", content)
            content = content.rstrip("`").strip()
        data = json.loads(content)
        budget = data.get("budget")
        if isinstance(budget, str):
            budget = int(re.sub(r"[^\d]", "", budget) or "0") or None
        top_results = data.get("top_results", 3)
        try:
            top_results = int(top_results)
        except (TypeError, ValueError):
            top_results = 3
        return {
            "source": _clean_city(str(data.get("source") or "")) or None,
            "destination": _clean_city(str(data.get("destination") or "")) or None,
            "budget": budget,
            "currency": data.get("currency") or "INR",
            "top_results": max(1, top_results),
        }
    except Exception:
        # Missing package, bad key, network error, or bad JSON → use rules.
        return None


def extract_travel_details(user_request: str) -> Dict[str, Any]:
    """Try LLM first (if a key exists), otherwise use regex/rules."""
    parsed = parse_with_llm(user_request)
    if parsed is None:
        parsed = parse_with_rules(user_request)
    return parsed


def parse_request(state: Dict[str, Any]) -> Dict[str, Any]:
    """AGENT 1: understand the natural-language request."""
    banner("🤖 AGENT 1: REQUEST PARSER")
    print("Understanding your request...")
    print()

    if is_demo_mode():
        print("⚙ No OpenAI API key found. Using DEMO MODE (rule-based parsing).")
        print()

    parsed = extract_travel_details(state.get("user_request", ""))
    source = parsed.get("source")
    destination = parsed.get("destination")
    budget = parsed.get("budget")
    top_results = parsed.get("top_results") or 3
    currency = parsed.get("currency") or "INR"

    missing = []
    if not source:
        missing.append("source city")
    if not destination:
        missing.append("destination city")
    if not budget or budget <= 0:
        missing.append("valid budget")

    if missing:
        print("❌ I could not extract:", ", ".join(missing) + ".")
        print("Please include source, destination, and a numeric budget.")
        print("Example: Find me the cheapest flight from Pune to Singapore under ₹30,000 and email me the top 3 options.")
        return {
            "source": source,
            "destination": destination,
            "budget": budget,
            "currency": currency,
            "top_results": top_results,
            "status": "missing_info",
        }

    print(f"✓ Source: {source}")
    print(f"✓ Destination: {destination}")
    print(f"✓ Budget: {format_inr(budget)}")
    print(f"✓ Requested Results: Top {top_results}")

    return {
        "source": source,
        "destination": destination,
        "budget": budget,
        "currency": currency,
        "top_results": top_results,
        "status": "parsed",
    }


def apply_memory(state: Dict[str, Any]) -> Dict[str, Any]:
    """UNIT 3: merge short-term session memory with parsed request details."""
    banner("🧠 SHORT-TERM MEMORY (UNIT III)")
    print("Checking conversational memory for this session...")
    print()

    snapshot = state.get("memory_snapshot") or {}
    memory = ConversationMemory()
    if snapshot:
        memory.source = snapshot.get("source")
        memory.destination = snapshot.get("destination")
        memory.budget = snapshot.get("budget")
        memory.currency = snapshot.get("currency") or "INR"
        memory.top_results = snapshot.get("top_results") or 3
        memory.last_user_request = snapshot.get("last_request") or ""
        memory.previous_selected_flights = list(snapshot.get("previous_selected_flights") or [])

    merged = apply_memory_to_state(state, memory)
    note = merged.get("memory_note") or ""

    if merged.get("status") == "parsed":
        print("✓ Memory applied successfully.")
        if note:
            print(f"✓ {note}")
        print()
        print(f"✓ Source: {merged['source']}")
        print(f"✓ Destination: {merged['destination']}")
        print(f"✓ Budget: {format_inr(merged['budget'])}")
        print(f"✓ Results to return: Top {merged['top_results']}")
    else:
        print("❌ Still missing information after memory merge.")
        if note:
            print(f"   {note}")

    return merged


def create_plan(state: Dict[str, Any]) -> Dict[str, Any]:
    """AGENT 2: create a multi-step execution plan (this is planning)."""
    banner("🧠 AGENT 2: PLANNING AGENT")
    print("Creating execution plan...")
    print()

    source = state.get("source")
    destination = state.get("destination")
    budget = state.get("budget")
    top_results = state.get("top_results", 3)

    plan = [
        f"Identify source and destination ({source} → {destination}).",
        "Search available flights using the Flight Search Tool.",
        "Collect flight details and prices.",
        f"Filter flights within the user's budget of {format_inr(budget)}.",
        "Sort flights from cheapest to most expensive.",
        f"Select the top {top_results} cheapest flights.",
        "Generate an email summary.",
        "Send or simulate sending the email.",
    ]

    print("I will perform the following tasks:")
    print()
    for index, step in enumerate(plan, start=1):
        print(f"{index}. {step}")

    return {"plan": plan, "status": "planned"}


def search_flights(state: Dict[str, Any]) -> Dict[str, Any]:
    """AGENT 3: call the Flight Search Tool (this is tool calling)."""
    banner("🔧 AGENT 3: FLIGHT SEARCH AGENT")
    print("Calling Flight Search Tool...")

    flights = flight_search_tool(state["source"], state["destination"])

    print("✓ Tool executed successfully.")
    print(f"✓ Found {len(flights)} flights.")

    return {"all_flights": flights, "status": "searched"}


def analyze_flights(state: Dict[str, Any]) -> Dict[str, Any]:
    """AGENT 4: filter, sort, and choose top flights (this is decision making)."""
    banner("📊 AGENT 4: FLIGHT ANALYSIS AGENT")
    print("Analyzing flight data...")
    print()

    budget = state["budget"]
    top_results = state.get("top_results", 3)
    all_flights: List[Dict[str, Any]] = list(state.get("all_flights") or [])

    within_budget = [flight for flight in all_flights if flight["price"] <= budget]
    removed = len(all_flights) - len(within_budget)
    sorted_flights = sorted(within_budget, key=lambda flight: flight["price"])
    selected = sorted_flights[:top_results]

    print(f"User Budget: {format_inr(budget)}")
    print()
    print(f"Total Flights: {len(all_flights)}")
    print()
    print(f"Flights Removed Above Budget: {removed}")
    print()
    print(f"Flights Remaining: {len(within_budget)}")
    print()

    if not selected:
        print("❌ No flights were found within your budget.")
        print()
        print("Try increasing your budget or changing your destination.")
        return {
            "filtered_flights": [],
            "selected_flights": [],
            "status": "no_flights",
        }

    print(f"Selecting Top {len(selected)} Cheapest Flights...")
    print()
    print("✓ Removed flights above budget.")
    print("✓ Sorted flights by lowest price.")
    print(f"✓ Selected top {len(selected)} cheapest flights.")
    print()
    print(f"🏆 TOP {len(selected)} CHEAPEST FLIGHTS")
    print()
    print(LINE)

    for index, flight in enumerate(selected, start=1):
        medal = MEDALS[index - 1] if index <= len(MEDALS) else "✈️"
        print()
        print(f"{medal} OPTION {index}")
        print()
        print(f"Airline: {flight['airline']}")
        print(f"Flight Number: {flight['flight_number']}")
        print(f"Departure: {flight['departure']}")
        print(f"Arrival: {flight['arrival']}")
        print(f"Duration: {flight['duration']}")
        print(f"Stops: {flight['stops']}")
        print(f"Price: {format_inr(flight['price'])}")
        print()
        print(LINE)

    return {
        "filtered_flights": sorted_flights,
        "selected_flights": selected,
        "status": "analyzed",
    }


def human_approval(state: Dict[str, Any]) -> Dict[str, Any]:
    """UNIT 4: human-in-the-loop before sending or generating the final email."""
    banner("👤 HUMAN-IN-THE-LOOP APPROVAL (UNIT IV)")
    selected = state.get("selected_flights") or []
    ui_mode = state.get("ui_mode") or "terminal"

    print("🤖 Agent Recommendation")
    print()
    print("The agent selected these flights:")
    print()
    for index, flight in enumerate(selected, start=1):
        print(f"{index}. {flight['airline']} — {format_inr(flight['price'])} ({flight['flight_number']})")
    print()

    approved = state.get("human_approved")

    if ui_mode == "streamlit":
        if approved is True:
            print("✓ Human approval received (web UI).")
            return {"status": "approved"}
        if approved is False:
            print("❌ Recommendation rejected by user (web UI).")
            return {"status": "rejected"}
        print("⏳ Waiting for human approval in the web interface...")
        return {"status": "awaiting_approval"}

    if approved is True:
        print("✓ Human approval received.")
        return {"status": "approved"}
    if approved is False:
        print("❌ Recommendation rejected.")
        return {"status": "rejected"}

    print("Do you want to proceed with these recommendations?")
    print("Type y to approve, n to reject:")
    print(">")
    try:
        answer = input().strip().lower()
    except EOFError:
        answer = "y"
    if answer in {"y", "yes"}:
        print("✓ Human approval received.")
        return {"status": "approved"}
    print("❌ Recommendation rejected.")
    return {"status": "rejected"}


def generate_email(state: Dict[str, Any]) -> Dict[str, Any]:
    """AGENT 5: write the email and send/simulate it (this is the final action)."""
    banner("📧 AGENT 5: EMAIL AGENT")

    source = state["source"]
    destination = state["destination"]
    budget = state["budget"]
    top_results = state.get("top_results", 3)
    selected = state.get("selected_flights") or []
    to_address = state.get("email_address") or "user@example.com"

    option_lines = []
    for index, flight in enumerate(selected, start=1):
        option_lines.append(
            f"{index}. {flight['airline']} – {format_inr(flight['price'])} "
            f"({flight['flight_number']}, {flight['departure']} → {flight['arrival']}, "
            f"{flight['duration']}, stops: {flight['stops']})"
        )

    subject = f"Top {len(selected)} Cheapest Flights from {source} to {destination}"
    body = (
        f"Hello,\n\n"
        f"I searched for flights from {source} to {destination} "
        f"within your budget of {format_inr(budget)}.\n\n"
        f"Here are the top {len(selected)} cheapest options:\n\n"
        + "\n".join(option_lines)
        + "\n\nThank you for using Flight Search AI Agent.\n\n"
        "Best regards,\n"
        "Flight Search AI Agent\n"
    )

    print(LINE)
    print("📧 EMAIL AGENT")
    print(LINE)
    print()
    print(f"To: {to_address}")
    print()
    print("Subject:")
    print(subject)
    print()
    print(body)

    delivery = send_email_tool(to_address, subject, body)

    return {
        "email_content": f"Subject: {subject}\n\n{body}",
        "status": "completed" if delivery else "completed",
    }
