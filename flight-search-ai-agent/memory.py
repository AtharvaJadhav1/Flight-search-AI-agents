"""
Short-term session memory for multi-turn flight search (not LangGraph shared state).

SHOW_ALL_RESULTS (0) means return every flight within budget on the initial search.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from tools import format_inr

# 0 = show all flights within budget; >0 = limit to top N after sorting
SHOW_ALL_RESULTS = 0


class ConversationMemory:
    """In-memory store for the current application session."""

    def __init__(self) -> None:
        self.source: Optional[str] = None
        self.destination: Optional[str] = None
        self.budget: Optional[int] = None
        self.currency: str = "INR"
        self.top_results: int = SHOW_ALL_RESULTS
        self.sort_by: str = "price"
        self.max_stops: Optional[int] = None
        self.last_user_request: str = ""
        self.previous_selected_flights: List[Dict[str, Any]] = []
        self.previous_filtered_flights: List[Dict[str, Any]] = []
        self.last_all_flights_count: int = 0
        self.refinement_count: int = 0

    def update_from_state(self, state: Dict[str, Any]) -> None:
        if state.get("source"):
            self.source = state["source"]
        if state.get("destination"):
            self.destination = state["destination"]
        if state.get("budget"):
            self.budget = state["budget"]
        if state.get("currency"):
            self.currency = state["currency"]
        if "top_results" in state and state["top_results"] is not None:
            self.top_results = int(state["top_results"])
        if state.get("sort_by"):
            self.sort_by = state["sort_by"]
        if state.get("max_stops") is not None:
            self.max_stops = state["max_stops"]
        if state.get("user_request"):
            self.last_user_request = state["user_request"]
        if state.get("selected_flights"):
            self.previous_selected_flights = list(state["selected_flights"])
        if state.get("filtered_flights"):
            self.previous_filtered_flights = list(state["filtered_flights"])
        if state.get("all_flights"):
            self.last_all_flights_count = len(state["all_flights"])

    def has_search_context(self) -> bool:
        return bool(self.source and self.destination and self.budget and self.budget > 0)

    def to_display_dict(self) -> Dict[str, Any]:
        filter_label = "Nonstop" if self.max_stops == 0 else "Any stops"
        sort_label = "Fastest" if self.sort_by == "duration" else "Cheapest"
        top_label = "All in budget" if self.top_results == SHOW_ALL_RESULTS else str(self.top_results)
        return {
            "source": self.source,
            "destination": self.destination,
            "budget": self.budget,
            "currency": self.currency,
            "top_results": top_label,
            "sort_by": sort_label,
            "filter": filter_label,
            "last_request": self.last_user_request,
            "has_previous_results": bool(self.previous_selected_flights),
            "results_count": self.last_all_flights_count,
            "conversation_turns": self.refinement_count,
        }

    def clear(self) -> None:
        self.__init__()


def _message_lower(text: str) -> str:
    return text.lower().strip()


def is_send_results_intent(text: str) -> bool:
    lower = _message_lower(text)
    patterns = (
        r"send\s+(?:me\s+)?(?:the\s+)?results",
        r"email\s+(?:me\s+)?(?:the\s+)?(?:results|these|them)",
        r"send\s+(?:me\s+)?(?:an?\s+)?email",
        r"approve\s+(?:and\s+)?send",
    )
    return any(re.search(p, lower) for p in patterns)


def is_new_search_message(text: str, parsed: Dict[str, Any]) -> bool:
    lower = _message_lower(text)
    if re.search(r"\b(now|instead)\b.*\b(find|search|flights)\b", lower):
        return bool(parsed.get("source") and parsed.get("destination"))
    source = parsed.get("source")
    destination = parsed.get("destination")
    budget = parsed.get("budget")
    if not source or not destination or not budget or budget <= 0:
        return False
    route_phrase = re.search(
        r"(?:from\s+\w[\w\s]{0,30}?\s+to\s+\w[\w\s]{0,30}?|"
        r"\w[\w\s]{0,20}?\s+to\s+\w[\w\s]{0,20}?\s+under)",
        lower,
    )
    return bool(route_phrase)


def is_follow_up_message(text: str, parsed: Dict[str, Any]) -> bool:
    if is_new_search_message(text, parsed):
        return False
    if is_send_results_intent(text):
        return True

    lower = _message_lower(text)
    refinement_signals = (
        r"give\s+me\s+(?:the\s+)?cheapest",
        r"cheapest",
        r"fastest",
        r"shortest",
        r"quickest",
        r"non-?stop",
        r"\bdirect\b",
        r"top\s+\d+",
        r"only\s+(?:the\s+)?\d+",
        r"show\s+me\s+only",
        r"same\s+route",
        r"previous\s+search",
        r"last\s+search",
        r"compare",
        r"filter",
    )
    return any(re.search(p, lower) for p in refinement_signals)


def apply_instruction_overrides(user_request: str, merged: Dict[str, Any], *, is_follow_up: bool) -> Dict[str, Any]:
    lower = _message_lower(user_request)

    if re.search(r"\b(fastest|shortest|quickest)\b", lower):
        merged["sort_by"] = "duration"
    elif re.search(r"\b(cheapest|lowest\s+price)\b", lower):
        merged["sort_by"] = "price"

    if re.search(r"\b(non-?stop|direct)\b", lower):
        merged["max_stops"] = 0

    top_match = re.search(r"top\s+(\d+)", lower)
    if top_match:
        merged["top_results"] = max(1, int(top_match.group(1)))
    elif re.search(r"cheapest\s+(\d+)", lower):
        merged["top_results"] = max(1, int(re.search(r"cheapest\s+(\d+)", lower).group(1)))
    elif re.search(
        r"(?:give\s+me\s+(?:the\s+)?|only\s+(?:the\s+)?)?(?:cheapest|fastest)\s+(?:one|1|flight)\b|"
        r"show\s+me\s+only\s+the\s+cheapest\s+one",
        lower,
    ):
        merged["top_results"] = 1
    elif re.search(r"only\s+the\s+cheapest\s+(\d+)", lower):
        merged["top_results"] = max(1, int(re.search(r"only\s+the\s+cheapest\s+(\d+)", lower).group(1)))
    elif re.search(r"only\s+(?:show\s+)?(\d+)", lower):
        merged["top_results"] = max(1, int(re.search(r"only\s+(?:show\s+)?(\d+)", lower).group(1)))
    elif is_follow_up and re.search(r"\bcheapest\b", lower) and merged.get("top_results") == SHOW_ALL_RESULTS:
        merged["top_results"] = 1

    return merged


def apply_memory_to_state(state: Dict[str, Any], memory: ConversationMemory) -> Dict[str, Any]:
    user_request = (state.get("user_request") or "").strip()
    parsed_snapshot = {
        "source": state.get("source"),
        "destination": state.get("destination"),
        "budget": state.get("budget"),
    }

    source = state.get("source")
    destination = state.get("destination")
    budget = state.get("budget")
    top_results = state.get("top_results")
    if top_results is None:
        top_results = memory.top_results
    currency = state.get("currency") or memory.currency or "INR"
    max_stops = state.get("max_stops")
    sort_by = state.get("sort_by") or memory.sort_by or "price"
    status = state.get("status", "")

    new_search = is_new_search_message(user_request, parsed_snapshot)
    follow_up = is_follow_up_message(user_request, parsed_snapshot)
    memory_note = ""

    if new_search:
        memory_note = f"New search: {source} → {destination}, budget {format_inr(budget)}."
        if top_results is None or (top_results == 3 and not re.search(r"top\s+\d+", user_request.lower())):
            top_results = SHOW_ALL_RESULTS
    elif follow_up:
        if not memory.has_search_context():
            return {
                "source": source,
                "destination": destination,
                "budget": budget,
                "currency": currency,
                "top_results": top_results,
                "max_stops": max_stops,
                "sort_by": sort_by,
                "status": "missing_info",
                "memory_note": (
                    "No previous flight search in this session. "
                    "Start with a route and budget, e.g. Pune to Singapore under ₹30,000."
                ),
                "conversation_intent": "need_context",
            }
        if not source:
            source = memory.source
        if not destination:
            destination = memory.destination
        if not budget or budget <= 0:
            budget = memory.budget
        if max_stops is None:
            max_stops = memory.max_stops
        if not state.get("sort_by"):
            sort_by = memory.sort_by or "price"
        memory_note = (
            f"Using session context: {source} → {destination}, budget {format_inr(budget)}."
        )
    elif status == "missing_info":
        gave_partial = bool(source or destination or budget)
        if gave_partial and memory.has_search_context():
            if not source:
                source = memory.source
            if not destination:
                destination = memory.destination
            if not budget or budget <= 0:
                budget = memory.budget
            memory_note = "Filled missing fields from session memory."
            follow_up = True
        else:
            return {
                "source": source,
                "destination": destination,
                "budget": budget,
                "currency": currency,
                "top_results": top_results,
                "max_stops": max_stops,
                "sort_by": sort_by,
                "status": "missing_info",
                "memory_note": "Could not resolve request from memory.",
                "conversation_intent": "",
            }
    elif status == "parsed" and not follow_up and not new_search:
        memory_note = ""

    merged = {
        "source": source,
        "destination": destination,
        "budget": budget,
        "currency": currency,
        "top_results": top_results,
        "max_stops": max_stops,
        "sort_by": sort_by,
        "status": "parsed",
        "memory_note": memory_note if follow_up or new_search else "",
        "conversation_intent": "send_results" if is_send_results_intent(user_request) else "search",
    }

    if follow_up or new_search:
        merged = apply_instruction_overrides(user_request, merged, is_follow_up=follow_up)

    missing = []
    if not merged.get("source"):
        missing.append("source city")
    if not merged.get("destination"):
        missing.append("destination city")
    if not merged.get("budget") or merged["budget"] <= 0:
        missing.append("valid budget")

    if missing:
        hint = (
            "Which route and budget would you like? Example: Mumbai to Dubai under ₹40,000."
            if "source" in missing or "destination" in missing
            else "Please include a budget amount."
        )
        merged["status"] = "missing_info"
        merged["memory_note"] = hint
        return merged

    if follow_up:
        instr = []
        tr = merged.get("top_results")
        if tr and tr > 0:
            instr.append(f"top {tr}")
        elif tr == SHOW_ALL_RESULTS:
            instr.append("all in budget")
        if merged.get("sort_by") == "duration":
            instr.append("fastest first")
        elif merged.get("sort_by") == "price":
            instr.append("cheapest first")
        if merged.get("max_stops") == 0:
            instr.append("nonstop only")
        if instr:
            merged["memory_note"] += " Applying: " + ", ".join(instr) + "."

    return merged


def memory_for_streamlit() -> ConversationMemory:
    import streamlit as st

    if "conversation_memory" not in st.session_state:
        st.session_state.conversation_memory = ConversationMemory()
    return st.session_state.conversation_memory
