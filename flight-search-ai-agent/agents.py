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
from tools import flight_search_tool, format_inr, parse_duration_minutes, send_email_tool
from ui_common import is_terminal_ui


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


def banner(title: str, state: Optional[Dict[str, Any]] = None) -> None:
    if not is_terminal_ui(state):
        return
    print()
    print("=" * 49)
    print(title)
    print("=" * 49)
    print()


def tprint(state: Dict[str, Any], *parts: object, sep: str = " ") -> None:
    """Print only in terminal UI mode."""
    if is_terminal_ui(state):
        print(sep.join(str(p) for p in parts))


def _clean_city(name: str) -> str:
    name = name.strip(" .,!?;:'\"")
    name = re.sub(r"\s+", " ", name)
    return name.title()


CITY_STOP_WORDS = (
    "under|below|within|and|with|for|on|in|by|at|next|this|tomorrow|today|"
    "please|nonstop|non-stop|direct|cheapest|budget|upto|up|less|email|send|show|top"
)


def _trim_city(raw: str) -> str:
    """Cut a captured city phrase at the first filler word ("Singapore for 2 adults" -> "Singapore")."""
    words = re.split(rf"\s+(?=(?:{CITY_STOP_WORDS})\b)", raw.strip(), maxsplit=1, flags=re.IGNORECASE)
    return words[0]


def _parse_amount(raw: str, suffix: str = "") -> Optional[int]:
    try:
        value = float(raw.replace(",", ""))
    except ValueError:
        return None
    if suffix.lower() == "k":
        value *= 1000
    elif suffix.lower() in {"l", "lakh", "lakhs"}:
        value *= 100000
    return int(value) if value > 0 else None


def add_trace(state: Dict[str, Any], agent: str, detail: str) -> List[Dict[str, str]]:
    """Append one entry to the agent activity log shown in the UI."""
    return list(state.get("trace") or []) + [{"agent": agent, "detail": detail}]


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
        source = _clean_city(_trim_city(from_to.group(1)))
        destination = _clean_city(_trim_city(from_to.group(2)))

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
    amount = r"([\d][\d,]*(?:\.\d+)?)\s*(k|lakhs?|l)?\b"
    for pattern in (
        rf"(?:under|below|within|less than|budget(?: of)?|upto|up to|max(?:imum)?)\s*(?:₹|rs\.?|inr)?\s*{amount}",
        rf"(?:₹|rs\.?|inr)\s*{amount}",
        rf"{amount}\s*(?:rupees|inr)",
    ):
        budget_match = re.search(pattern, lower)
        if budget_match:
            budget = _parse_amount(budget_match.group(1), budget_match.group(2) or "")
            break

    from memory import SHOW_ALL_RESULTS

    top_results = SHOW_ALL_RESULTS
    top_match = re.search(r"top\s+(\d+)", lower)
    if top_match:
        top_results = max(1, int(top_match.group(1)))
    else:
        show_match = re.search(r"(?:show|email|send)\s+(?:me\s+)?(\d+)", lower)
        if show_match:
            top_results = max(1, int(show_match.group(1)))

    max_stops = 0 if re.search(r"\b(non-?stop|direct)\b", lower) else None
    sort_by = "duration" if re.search(r"\b(fastest|shortest|quickest)\b", lower) else None

    return {
        "source": source,
        "destination": destination,
        "budget": budget,
        "currency": currency,
        "top_results": top_results,
        "max_stops": max_stops,
        "sort_by": sort_by,
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
            "currency, top_results, max_stops, sort_by. budget must be an integer. "
            "max_stops is 0 for nonstop/direct requests, otherwise null. "
            "sort_by is \"duration\" if the user wants the fastest flights, otherwise null. "
            "currency should be INR unless another currency is clearly mentioned. "
            "top_results should be 0 if the user did not ask for a specific number of results "
            "(0 means list all flights within budget); otherwise use the requested count.\n\n"
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
        from memory import SHOW_ALL_RESULTS

        top_results = data.get("top_results", SHOW_ALL_RESULTS)
        try:
            top_results = int(top_results)
        except (TypeError, ValueError):
            top_results = SHOW_ALL_RESULTS
        if top_results < 0:
            top_results = SHOW_ALL_RESULTS
        return {
            "source": _clean_city(str(data.get("source") or "")) or None,
            "destination": _clean_city(str(data.get("destination") or "")) or None,
            "budget": budget,
            "currency": data.get("currency") or "INR",
            "top_results": top_results if top_results == SHOW_ALL_RESULTS else max(1, top_results),
            "max_stops": data.get("max_stops") if isinstance(data.get("max_stops"), int) else None,
            "sort_by": "duration" if data.get("sort_by") == "duration" else None,
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
    banner("🤖 AGENT 1: REQUEST PARSER", state)
    tprint(state, "Understanding your request...")
    if is_terminal_ui(state):
        print()

    if is_demo_mode() and is_terminal_ui(state):
        print("⚙ No OpenAI API key found. Using DEMO MODE (rule-based parsing).")
        print()

    parsed = extract_travel_details(state.get("user_request", ""))
    source = parsed.get("source")
    destination = parsed.get("destination")
    budget = parsed.get("budget")
    from memory import SHOW_ALL_RESULTS

    top_results = parsed.get("top_results")
    if top_results is None:
        top_results = SHOW_ALL_RESULTS
    currency = parsed.get("currency") or "INR"
    prefs = state.get("prefs") or {}
    max_stops = parsed.get("max_stops")
    if max_stops is None:
        max_stops = prefs.get("max_stops")
    sort_by = parsed.get("sort_by") or prefs.get("sort_by") or "price"

    missing = []
    if not source:
        missing.append("source city")
    if not destination:
        missing.append("destination city")
    if not budget or budget <= 0:
        missing.append("valid budget")

    if missing:
        if is_terminal_ui(state):
            print("❌ I could not extract:", ", ".join(missing) + ".")
            print("Please include source, destination, and a numeric budget.")
            print(
                "Example: Find me the cheapest flight from Pune to Singapore "
                "under ₹30,000 and email me the top 3 options."
            )
        return {
            "source": source,
            "destination": destination,
            "budget": budget,
            "currency": currency,
            "top_results": top_results,
            "max_stops": max_stops,
            "sort_by": sort_by,
            "status": "missing_info",
            "trace": add_trace(
                state, "Request Parser", "Could not extract: " + ", ".join(missing) + "."
            ),
        }

    if is_terminal_ui(state):
        print(f"✓ Source: {source}")
        print(f"✓ Destination: {destination}")
        print(f"✓ Budget: {format_inr(budget)}")
        if top_results == SHOW_ALL_RESULTS:
            print("✓ Requested Results: All flights within budget")
        else:
            print(f"✓ Requested Results: Top {top_results}")

    return {
        "source": source,
        "destination": destination,
        "budget": budget,
        "currency": currency,
        "top_results": top_results,
        "max_stops": max_stops,
        "sort_by": sort_by,
        "status": "parsed",
        "trace": add_trace(
            state,
            "Request Parser",
            f"{source} → {destination}, budget {format_inr(budget)}, top {top_results}"
            + (", nonstop only" if max_stops == 0 else "")
            + (", fastest first" if sort_by == "duration" else "")
            + f" ({'rule-based' if is_demo_mode() else 'LLM'} parsing).",
        ),
    }


def apply_memory(state: Dict[str, Any]) -> Dict[str, Any]:
    """Merge short-term session memory with parsed request details."""
    from memory import SHOW_ALL_RESULTS

    banner("🧠 SESSION MEMORY", state)
    tprint(state, "Checking conversational memory for this session...")
    if is_terminal_ui(state):
        print()

    snapshot = state.get("memory_snapshot") or {}
    memory = ConversationMemory()
    if snapshot:
        memory.source = snapshot.get("source")
        memory.destination = snapshot.get("destination")
        memory.budget = snapshot.get("budget")
        memory.currency = snapshot.get("currency") or "INR"
        snap_top = snapshot.get("top_results")
        memory.top_results = snap_top if snap_top is not None else SHOW_ALL_RESULTS
        memory.last_user_request = snapshot.get("last_request") or ""
        memory.previous_selected_flights = list(snapshot.get("previous_selected_flights") or [])

    merged = apply_memory_to_state(state, memory)
    note = merged.get("memory_note") or ""
    if merged.get("status") == "parsed":
        trace_detail = note or "No earlier context needed for this request."
        if "Retrieved context" in trace_detail:
            trace_detail = (
                "Retrieved previous conversation context. "
                + trace_detail.split(". ", 1)[-1]
            )
    else:
        trace_detail = note or "Could not merge session memory."
    merged["trace"] = add_trace(state, "Session Memory", trace_detail)

    if merged.get("status") == "parsed":
        if is_terminal_ui(state):
            print("✓ Memory applied successfully.")
            if note:
                print(f"✓ {note}")
            print()
            print(f"✓ Source: {merged['source']}")
            print(f"✓ Destination: {merged['destination']}")
            print(f"✓ Budget: {format_inr(merged['budget'])}")
            tr = merged["top_results"]
            if tr == SHOW_ALL_RESULTS:
                print("✓ Results to return: All flights within budget")
            else:
                print(f"✓ Results to return: Top {tr}")
    elif is_terminal_ui(state):
        print("❌ Still missing information after memory merge.")
        if note:
            print(f"   {note}")

    return merged


def create_plan(state: Dict[str, Any]) -> Dict[str, Any]:
    """AGENT 2: create a multi-step execution plan (this is planning)."""
    banner("🧠 AGENT 2: PLANNING AGENT", state)
    tprint(state, "Creating execution plan...")
    if is_terminal_ui(state):
        print()

    source = state.get("source")
    destination = state.get("destination")
    budget = state.get("budget")
    from memory import SHOW_ALL_RESULTS

    top_results = state.get("top_results", SHOW_ALL_RESULTS)

    plan = [
        f"Identify source and destination ({source} → {destination}).",
        "Search available flights using the Flight Search Tool.",
        "Collect flight details and prices.",
        f"Filter flights within the user's budget of {format_inr(budget)}"
        + (" (nonstop only)." if state.get("max_stops") == 0 else "."),
        "Sort flights from fastest to slowest."
        if state.get("sort_by") == "duration"
        else "Sort flights from cheapest to most expensive.",
        "List all flights within budget."
        if top_results == 0
        else f"Select the top {top_results} flights.",
        "Generate an email summary.",
        "Send or simulate sending the email.",
    ]

    if is_terminal_ui(state):
        print("I will perform the following tasks:")
        print()
        for index, step in enumerate(plan, start=1):
            print(f"{index}. {step}")

    return {
        "plan": plan,
        "status": "planned",
        "trace": add_trace(state, "Planning Agent", f"Created a {len(plan)}-step plan."),
    }


def search_flights(state: Dict[str, Any]) -> Dict[str, Any]:
    """AGENT 3: call the Flight Search Tool (this is tool calling)."""
    banner("🔧 AGENT 3: FLIGHT SEARCH AGENT", state)
    tprint(state, "Calling Flight Search Tool...")

    quiet = not is_terminal_ui(state)
    flights = flight_search_tool(state["source"], state["destination"], quiet=quiet)

    if is_terminal_ui(state):
        print("✓ Tool executed successfully.")
        print(f"✓ Found {len(flights)} flights.")

    return {
        "all_flights": flights,
        "status": "searched",
        "trace": add_trace(
            state,
            "Flight Search Agent",
            f"Flight Search Tool returned {len(flights)} flights for "
            f"{state['source']} → {state['destination']}.",
        ),
    }


def analyze_flights(state: Dict[str, Any]) -> Dict[str, Any]:
    """AGENT 4: filter, sort, and choose top flights (this is decision making)."""
    banner("📊 AGENT 4: FLIGHT ANALYSIS AGENT", state)
    tprint(state, "Analyzing flight data...")
    if is_terminal_ui(state):
        print()

    budget = state["budget"]
    from memory import SHOW_ALL_RESULTS

    top_results = state.get("top_results", SHOW_ALL_RESULTS)
    all_flights: List[Dict[str, Any]] = list(state.get("all_flights") or [])

    max_stops = state.get("max_stops")
    sort_by = state.get("sort_by") or "price"

    within_budget = [flight for flight in all_flights if flight["price"] <= budget]
    removed = len(all_flights) - len(within_budget)
    if max_stops is not None:
        within_budget = [f for f in within_budget if f["stops"] <= max_stops]
    if sort_by == "duration":
        key = lambda f: (parse_duration_minutes(f["duration"]), f["price"])  # noqa: E731
    else:
        key = lambda f: (f["price"], parse_duration_minutes(f["duration"]))  # noqa: E731
    sorted_flights = sorted(within_budget, key=key)
    if top_results == SHOW_ALL_RESULTS or top_results <= 0:
        selected = sorted_flights
        pick_label = f"all {len(selected)} in budget"
    else:
        selected = sorted_flights[:top_results]
        pick_label = f"top {len(selected)} by {'duration' if sort_by == 'duration' else 'price'}"
    analysis_note = (
        f"{len(all_flights)} found, {removed} above budget"
        + (f", {len(all_flights) - removed - len(within_budget)} filtered by stops" if max_stops is not None else "")
        + f"; showing {pick_label}."
    )

    if is_terminal_ui(state):
        print(f"User Budget: {format_inr(budget)}")
        print()
        print(f"Total Flights: {len(all_flights)}")
        print()
        print(f"Flights Removed Above Budget: {removed}")
        print()
        print(f"Flights Remaining: {len(within_budget)}")
        print()

    if not selected:
        if is_terminal_ui(state):
            print("❌ No flights were found within your budget.")
            print()
            print("Try increasing your budget or changing your destination.")
        return {
            "filtered_flights": [],
            "selected_flights": [],
            "status": "no_flights",
            "trace": add_trace(state, "Flight Analysis Agent", analysis_note),
        }

    if is_terminal_ui(state):
        print(f"Selecting {len(selected)} flight(s)...")
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
        "trace": add_trace(state, "Flight Analysis Agent", analysis_note),
    }


def human_approval(state: Dict[str, Any]) -> Dict[str, Any]:
    """Human-in-the-loop before sending or generating the final email."""
    banner("👤 HUMAN APPROVAL", state)
    selected = state.get("selected_flights") or []
    ui_mode = state.get("ui_mode") or "terminal"

    if is_terminal_ui(state):
        print("🤖 Agent Recommendation")
        print()
        print("The agent selected these flights:")
        print()
        for index, flight in enumerate(selected, start=1):
            print(
                f"{index}. {flight['airline']} — {format_inr(flight['price'])} "
                f"({flight['flight_number']})"
            )
        print()

    approved = state.get("human_approved")

    if ui_mode == "streamlit":
        if approved is True:
            return {
                "status": "approved",
                "trace": add_trace(state, "Human Approval", "Approved by the user."),
            }
        if approved is False:
            return {
                "status": "rejected",
                "trace": add_trace(state, "Human Approval", "Rejected by the user; no email sent."),
            }
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


def build_email_draft(state: Dict[str, Any]) -> Dict[str, str]:
    """Compose the email subject and body (no sending)."""
    source = state["source"]
    destination = state["destination"]
    budget = state["budget"]
    selected = state.get("selected_flights") or []

    option_lines = []
    for index, flight in enumerate(selected, start=1):
        stops = "Nonstop" if flight["stops"] == 0 else f"{flight['stops']} stop(s)"
        option_lines.append(
            f"{index}. {flight['airline']} – {format_inr(flight['price'])} "
            f"({flight['flight_number']}, {flight['departure']} → {flight['arrival']}, "
            f"{flight['duration']}, {stops})"
        )

    subject = f"Top {len(selected)} Cheapest Flights from {source} to {destination}"
    if state.get("sort_by") == "duration":
        subject = f"Top {len(selected)} Fastest Flights from {source} to {destination}"
    body = (
        f"Hello,\n\n"
        f"I searched for flights from {source} to {destination} "
        f"within your budget of {format_inr(budget)}.\n\n"
        f"Here are the top {len(selected)} options:\n\n"
        + "\n".join(option_lines)
        + "\n\nThank you for using Flight Search AI Agent.\n\n"
        "Best regards,\n"
        "Flight Search AI Agent\n"
    )
    return {"subject": subject, "body": body}


def generate_email(state: Dict[str, Any]) -> Dict[str, Any]:
    """AGENT 5: write the email and send/simulate it (this is the final action)."""
    banner("📧 AGENT 5: EMAIL AGENT", state)

    to_address = state.get("email_address") or "user@example.com"
    draft = build_email_draft(state)
    # The user may have edited the draft in the web UI before approving.
    subject = state.get("email_subject_override") or draft["subject"]
    body = state.get("email_body_override") or draft["body"]

    if is_terminal_ui(state):
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

    quiet = not is_terminal_ui(state)
    delivery = send_email_tool(to_address, subject, body, quiet=quiet)

    return {
        "email_content": f"Subject: {subject}\n\n{body}",
        "email_delivery": delivery,
        "status": "completed",
        "trace": add_trace(
            state,
            "Email Agent",
            f"Email to {to_address} "
            + ("sent via SMTP." if delivery == "sent" else "simulated (Demo Mode, no SMTP configured)."),
        ),
    }
