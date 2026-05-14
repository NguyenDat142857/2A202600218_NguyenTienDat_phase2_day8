"""Routing utilities for LangGraph conditional edges.

These functions determine the next workflow node
based on the current graph state.

Design goals:
- deterministic routing,
- bounded retry behavior,
- safe fallbacks,
- explicit approval control,
- fault-tolerant execution.
"""

from __future__ import annotations

from .state import AgentState, Route


# =========================================================
# CLASSIFICATION ROUTING
# =========================================================

def route_after_classify(state: AgentState) -> str:
    """
    Route workflow after classification stage.

    Possible outputs:
    - answer
    - tool
    - clarify
    - risky_action
    - retry

    Unknown routes safely fallback to `clarify`.
    """

    route = str(
        state.get("route", Route.MISSING_INFO.value)
    ).lower()

    route_mapping = {
        Route.SIMPLE.value: "answer",
        Route.TOOL.value: "tool",
        Route.MISSING_INFO.value: "clarify",
        Route.RISKY.value: "risky_action",
        Route.ERROR.value: "retry",
    }

    return route_mapping.get(route, "clarify")


# =========================================================
# RETRY ROUTING
# =========================================================

def route_after_retry(state: AgentState) -> str:
    """
    Decide whether workflow should retry
    or escalate to dead-letter handling.

    Logic:
    - retry if attempt < max_attempts
    - otherwise dead_letter
    """

    attempt = int(state.get("attempt", 0))

    max_attempts = int(
        state.get("max_attempts", 3)
    )

    if attempt >= max_attempts:
        return "dead_letter"

    return "tool"


# =========================================================
# EVALUATION ROUTING
# =========================================================

def route_after_evaluate(state: AgentState) -> str:
    """
    Evaluate tool execution outcome.

    Returns:
    - retry
    - answer

    This acts as the workflow "done?" gate.
    """

    result = str(
        state.get("evaluation_result", "success")
    ).lower()

    if result == "needs_retry":
        return "retry"

    return "answer"


# =========================================================
# APPROVAL ROUTING
# =========================================================

def route_after_approval(state: AgentState) -> str:
    """
    Continue workflow only if approved.

    Supported approval states:
    - approved  -> tool
    - rejected  -> clarify
    - edited    -> clarify
    - unknown   -> clarify
    """

    approval = state.get("approval") or {}

    approved = bool(
        approval.get("approved", False)
    )

    if approved:
        return "tool"

    return "clarify"