"""LangGraph workflow construction.

This module builds and compiles the workflow graph while remaining import-safe.
LangGraph is imported only inside `build_graph()` so unit tests can still run
without requiring graph compilation during early development.

Architecture goals:
- Explicit node boundaries
- Safe retry loops
- Human-in-the-loop approval
- Deterministic routing
- Fault tolerance and recovery
- Auditability and observability
"""

from __future__ import annotations

from typing import Any

from .nodes import (
    answer_node,
    approval_node,
    ask_clarification_node,
    classify_node,
    dead_letter_node,
    evaluate_node,
    finalize_node,
    intake_node,
    retry_or_fallback_node,
    risky_action_node,
    tool_node,
)

from .routing import (
    route_after_approval,
    route_after_classify,
    route_after_evaluate,
    route_after_retry,
)

from .state import AgentState


# =========================================================
# GRAPH BUILDER
# =========================================================

def build_graph(checkpointer: Any | None = None):
    """
    Build and compile the LangGraph workflow.

    Workflow overview:
        START
          ↓
        intake
          ↓
        classify
          ├── simple → answer
          ├── tool → tool → evaluate
          ├── missing_info → clarify
          ├── risky → risky_action → approval
          └── error → retry

    Retry loop:
        tool → evaluate → retry → tool

    Safety guarantees:
    - Risky actions require approval
    - Retry loops are bounded
    - Failed executions escalate to dead_letter
    - Every path terminates through finalize
    """

    try:
        from langgraph.graph import (
            END,
            START,
            StateGraph,
        )

    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "LangGraph is required.\n"
            "Install with:\n"
            "pip install langgraph\n"
            "or\n"
            "pip install -e '.[dev]'"
        ) from exc

    # =====================================================
    # INITIALIZE GRAPH
    # =====================================================

    graph = StateGraph(AgentState)

    # =====================================================
    # REGISTER NODES
    # =====================================================

    graph.add_node("intake", intake_node)

    graph.add_node("classify", classify_node)

    graph.add_node("tool", tool_node)

    graph.add_node("evaluate", evaluate_node)

    graph.add_node("retry", retry_or_fallback_node)

    graph.add_node("clarify", ask_clarification_node)

    graph.add_node("risky_action", risky_action_node)

    graph.add_node("approval", approval_node)

    graph.add_node("answer", answer_node)

    graph.add_node("dead_letter", dead_letter_node)

    graph.add_node("finalize", finalize_node)

    # =====================================================
    # ENTRY FLOW
    # =====================================================

    graph.add_edge(START, "intake")

    graph.add_edge("intake", "classify")

    # =====================================================
    # ROUTING AFTER CLASSIFICATION
    # =====================================================

    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "answer": "answer",
            "tool": "tool",
            "clarify": "clarify",
            "risky_action": "risky_action",
            "retry": "retry",
        },
    )

    # =====================================================
    # TOOL EXECUTION FLOW
    # =====================================================

    graph.add_edge("tool", "evaluate")

    graph.add_conditional_edges(
        "evaluate",
        route_after_evaluate,
        {
            "answer": "answer",
            "retry": "retry",
        },
    )

    # =====================================================
    # RETRY FLOW
    # =====================================================

    graph.add_conditional_edges(
        "retry",
        route_after_retry,
        {
            "tool": "tool",
            "dead_letter": "dead_letter",
        },
    )

    # =====================================================
    # RISKY ACTION FLOW
    # =====================================================

    graph.add_edge("risky_action", "approval")

    graph.add_conditional_edges(
        "approval",
        route_after_approval,
        {
            "tool": "tool",
            "clarify": "clarify",
        },
    )

    # =====================================================
    # TERMINAL PATHS
    # =====================================================

    graph.add_edge("answer", "finalize")

    graph.add_edge("clarify", "finalize")

    graph.add_edge("dead_letter", "finalize")

    graph.add_edge("finalize", END)

    # =====================================================
    # COMPILE GRAPH
    # =====================================================

    compiled_graph = graph.compile(
        checkpointer=checkpointer,
    )

    return compiled_graph