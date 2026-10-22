"""UI helpers with no Streamlit dependency (safe for terminal imports)."""

from __future__ import annotations

from typing import Any, Dict, Optional


def is_terminal_ui(state: Optional[Dict[str, Any]]) -> bool:
    if not state:
        return True
    return state.get("ui_mode", "terminal") != "streamlit"
