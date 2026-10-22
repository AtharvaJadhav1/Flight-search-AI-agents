"""
Short-term conversational memory (Unit III).

Retains search context for the current session only — no database.
Works with Streamlit session_state and the terminal conversation loop.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class ConversationMemory:
    """In-memory store for the current application session."""

    def __init__(self) -> None:
        self.source: Optional[str] = None
        self.destination: Optional[str] = None
        self.budget: Optional[int] = None
        self.currency: str = "INR"
        self.top_results: int = 3
        self.last_user_request: str = ""
        self.previous_selected_flights: List[Dict[str, Any]] = []
        self.previous_filtered_flights: List[Dict[str, Any]] = []

    def update_from_state(self, state: Dict[str, Any]) -> None:
        """Remember fields from a completed or partial workflow run."""
        if state.get("source"):
            self.source = state["source"]
        if state.get("destination"):
            self.destination = state["destination"]
        if state.get("budget"):
            self.budget = state["budget"]
        if state.get("currency"):
            self.currency = state["currency"]
        if state.get("top_results"):
            self.top_results = int(state["top_results"])
        if state.get("user_request"):
            self.last_user_request = state["user_request"]
        if state.get("selected_flights"):
            self.previous_selected_flights = list(state["selected_flights"])
        if state.get("filtered_flights"):
            self.previous_filtered_flights = list(state["filtered_flights"])

    def to_display_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "destination": self.destination,
            "budget": self.budget,
            "currency": self.currency,
            "top_results": self.top_results,
            "last_request": self.last_user_request,
            "has_previous_results": bool(self.previous_selected_flights),
        }

    def clear(self) -> None:
        self.__init__()


def _is_follow_up_only_cheapest(text: str) -> bool:
    lower = text.lower().strip()
    patterns = [
        r"cheapest\s+one",
        r"only\s+the\s+cheapest",
        r"just\s+the\s+cheapest",
        r"show\s+(?:me\s+)?only\s+(?:the\s+)?cheapest",
        r"top\s+1\b",
        r"single\s+cheapest",
    ]
    return any(re.search(p, lower) for p in patterns)


def _is_refinement_request(text: str) -> bool:
    """True when the message likely refers to a prior search without repeating cities."""
    lower = text.lower().strip()
    if _is_follow_up_only_cheapest(lower):
        return True
    refinement_phrases = [
        "same route",
        "same search",
        "previous search",
        "last search",
        "those flights",
        "show me again",
        "email those",
    ]
    return any(phrase in lower for phrase in refinement_phrases)


def apply_memory_to_state(state: Dict[str, Any], memory: ConversationMemory) -> Dict[str, Any]:
    """
    Merge session memory into workflow state after the request parser.

    Fills missing source/destination/budget from the last successful search.
    Handles follow-ups like "Show me only the cheapest one."
    """
    user_request = (state.get("user_request") or "").strip()
    source = state.get("source")
    destination = state.get("destination")
    budget = state.get("budget")
    top_results = state.get("top_results") or memory.top_results or 3
    currency = state.get("currency") or memory.currency or "INR"
    status = state.get("status", "")

    follow_up = _is_refinement_request(user_request)

    # Fill gaps from memory for explicit follow-ups, or when the user gave at least
    # part of a new request (e.g. only a new budget). A message with no travel
    # details at all must not silently replay the previous search.
    gave_partial = bool(source or destination or budget)
    if follow_up or (status == "missing_info" and gave_partial):
        if not source and memory.source:
            source = memory.source
        if not destination and memory.destination:
            destination = memory.destination
        if (not budget or budget <= 0) and memory.budget:
            budget = memory.budget

    if _is_follow_up_only_cheapest(user_request):
        top_results = 1

    top_match = re.search(r"top\s+(\d+)", user_request.lower())
    if top_match:
        top_results = max(1, int(top_match.group(1)))

    missing = []
    if not source:
        missing.append("source city")
    if not destination:
        missing.append("destination city")
    if not budget or budget <= 0:
        missing.append("valid budget")

    memory_note = ""
    if follow_up and memory.source and memory.destination:
        memory_note = (
            f"Recalled prior context: {memory.source} → {memory.destination}, "
            f"budget {memory.budget}, top {top_results}."
        )

    if missing:
        return {
            "source": source,
            "destination": destination,
            "budget": budget,
            "currency": currency,
            "top_results": top_results,
            "status": "missing_info",
            "memory_note": memory_note or "Could not resolve request from memory.",
        }

    return {
        "source": source,
        "destination": destination,
        "budget": budget,
        "currency": currency,
        "top_results": top_results,
        "status": "parsed",
        "memory_note": memory_note,
    }


def memory_for_streamlit() -> ConversationMemory:
    """Return or create ConversationMemory bound to Streamlit session_state."""
    import streamlit as st

    if "conversation_memory" not in st.session_state:
        st.session_state.conversation_memory = ConversationMemory()
    return st.session_state.conversation_memory
