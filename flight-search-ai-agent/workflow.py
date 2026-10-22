"""
LangGraph workflow for the Flight Search AI Agent.

START → parse_request → apply_memory → create_plan → search_flights
     → analyze_flights → human_approval → generate_email → END

Conditional edges skip later steps when information is missing, no flights match,
approval is pending (web UI), or the user rejects recommendations.
"""

from typing import Any, Dict, List, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agents import (
    analyze_flights,
    apply_memory,
    create_plan,
    generate_email,
    human_approval,
    parse_request,
    search_flights,
)


class AgentState(TypedDict, total=False):
    """Shared memory that every agent can read and update."""

    user_request: str
    source: Optional[str]
    destination: Optional[str]
    budget: Optional[int]
    currency: str
    top_results: int
    plan: List[str]
    all_flights: List[Dict[str, Any]]
    filtered_flights: List[Dict[str, Any]]
    selected_flights: List[Dict[str, Any]]
    email_content: str
    email_address: str
    status: str
    ui_mode: str
    human_approved: Optional[bool]
    memory_note: str
    memory_snapshot: Dict[str, Any]
    max_stops: Optional[int]
    sort_by: str
    prefs: Dict[str, Any]
    trace: List[Dict[str, str]]
    email_delivery: str
    email_subject_override: str
    email_body_override: str
    conversation_intent: str


def after_parse(state: AgentState) -> str:
    """Always continue to memory merge (memory may fix missing_info)."""
    return "continue"


def after_memory(state: AgentState) -> str:
    if state.get("status") == "missing_info":
        return "stop"
    return "continue"


def after_analyze(state: AgentState) -> str:
    if state.get("status") == "no_flights":
        return "stop"
    return "continue"


def after_approval(state: AgentState) -> str:
    status = state.get("status", "")
    if status == "awaiting_approval":
        return "pause"
    if status == "rejected":
        return "stop"
    return "continue"


def _add_core_nodes(graph: StateGraph) -> None:
    graph.add_node("parse_request", parse_request)
    graph.add_node("apply_memory", apply_memory)
    graph.add_node("create_plan", create_plan)
    graph.add_node("search_flights", search_flights)
    graph.add_node("analyze_flights", analyze_flights)
    graph.add_node("human_approval", human_approval)
    graph.add_node("generate_email", generate_email)


def _add_core_edges(graph: StateGraph, *, include_approval: bool, include_email: bool) -> None:
    graph.add_edge(START, "parse_request")
    graph.add_conditional_edges(
        "parse_request",
        after_parse,
        {"continue": "apply_memory"},
    )
    graph.add_conditional_edges(
        "apply_memory",
        after_memory,
        {
            "continue": "create_plan",
            "stop": END,
        },
    )
    graph.add_edge("create_plan", "search_flights")
    graph.add_edge("search_flights", "analyze_flights")

    if not include_approval:
        graph.add_conditional_edges(
            "analyze_flights",
            after_analyze,
            {"continue": END, "stop": END},
        )
        return

    graph.add_conditional_edges(
        "analyze_flights",
        after_analyze,
        {
            "continue": "human_approval",
            "stop": END,
        },
    )

    if not include_email:
        graph.add_edge("human_approval", END)
        return

    graph.add_conditional_edges(
        "human_approval",
        after_approval,
        {
            "continue": "generate_email",
            "pause": END,
            "stop": END,
        },
    )
    graph.add_edge("generate_email", END)


def build_workflow(*, include_approval: bool = True, include_email: bool = True):
    """Create and compile the LangGraph StateGraph."""
    graph = StateGraph(AgentState)
    _add_core_nodes(graph)
    _add_core_edges(
        graph,
        include_approval=include_approval,
        include_email=include_email,
    )
    return graph.compile(checkpointer=MemorySaver())


# Terminal: full pipeline with interactive approval prompt.
flight_agent_app = build_workflow(include_approval=True, include_email=True)

# Streamlit: search + analysis only; approval and email run after UI buttons.
flight_agent_app_search = build_workflow(include_approval=False, include_email=False)

DEFAULT_THREAD_ID = "flight-search-session"


def initial_state(
    user_request: str,
    email_address: str,
    *,
    ui_mode: str = "terminal",
    human_approved: Optional[bool] = None,
    memory_snapshot: Optional[Dict[str, Any]] = None,
    prefs: Optional[Dict[str, Any]] = None,
) -> AgentState:
    return {
        "user_request": user_request,
        "email_address": email_address,
        "currency": "INR",
        "top_results": 0,
        "plan": [],
        "all_flights": [],
        "filtered_flights": [],
        "selected_flights": [],
        "email_content": "",
        "status": "started",
        "ui_mode": ui_mode,
        "human_approved": human_approved,
        "memory_note": "",
        "memory_snapshot": memory_snapshot or {},
        "max_stops": None,
        "sort_by": "price",
        "prefs": prefs or {},
        "trace": [],
        "email_delivery": "",
        "conversation_intent": "",
    }


def run_config(thread_id: str = DEFAULT_THREAD_ID) -> Dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}
