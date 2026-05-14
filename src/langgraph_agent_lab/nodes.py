"""Production-ready LangGraph workflow nodes.

Each node:
- is small and testable,
- returns partial state updates,
- avoids mutating input state,
- emits structured audit events,
- supports retry / approval / recovery flows.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any

from .state import (
    AgentState,
    ApprovalDecision,
    Route,
    make_event,
)

# =========================================================
# CONSTANTS
# =========================================================

RISKY_KEYWORDS = {
    "refund",
    "delete",
    "remove",
    "cancel",
    "revoke",
    "suspend",
    "disable",
    "terminate",
    "send",
    "export",
}

TOOL_KEYWORDS = {
    "status",
    "lookup",
    "track",
    "find",
    "search",
    "invoice",
    "shipment",
    "ticket",
    "order",
    "profile",
}

ERROR_KEYWORDS = {
    "timeout",
    "failure",
    "failed",
    "crash",
    "unavailable",
    "502",
    "503",
    "gateway",
    "database",
}

PII_PATTERNS = [
    r"\b\d{16}\b",                      # possible credit card
    r"\b\d{3}-\d{2}-\d{4}\b",          # SSN-like
    r"\b[\w\.-]+@[\w\.-]+\.\w+\b",     # email
]


# =========================================================
# HELPERS
# =========================================================

def normalize_text(text: str) -> str:
    """Normalize user input safely."""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def contains_pii(text: str) -> bool:
    """Simple PII detection."""
    return any(re.search(pattern, text) for pattern in PII_PATTERNS)


def has_keywords(text: str, keywords: set[str]) -> bool:
    """Check whether query contains keywords."""
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def create_message(role: str, content: str) -> str:
    """Create structured message string."""
    return f"{role}:{content}"


# =========================================================
# INTAKE NODE
# =========================================================

def intake_node(state: AgentState) -> dict[str, Any]:
    """
    Normalize and validate incoming request.
    """

    raw_query = state.get("query", "")
    query = normalize_text(raw_query)

    metadata = {
        "query_length": len(query),
        "contains_pii": contains_pii(query),
    }

    return {
        "query": query,
        "metadata": metadata,
        "messages": [
            create_message("intake", query[:100]),
        ],
        "events": [
            make_event(
                "intake",
                "completed",
                "query normalized and validated",
            )
        ],
    }


# =========================================================
# CLASSIFICATION NODE
# =========================================================

def classify_node(state: AgentState) -> dict[str, Any]:
    """
    Route requests into workflow categories.
    """

    query = state.get("query", "").lower()

    route = Route.SIMPLE
    risk_level = "low"

    if has_keywords(query, RISKY_KEYWORDS):
        route = Route.RISKY
        risk_level = "high"

    elif has_keywords(query, TOOL_KEYWORDS):
        route = Route.TOOL

    elif has_keywords(query, ERROR_KEYWORDS):
        route = Route.ERROR

    elif len(query.split()) < 4:
        route = Route.MISSING_INFO

    return {
        "route": route.value,
        "risk_level": risk_level,
        "events": [
            make_event(
                "classify",
                "completed",
                f"route={route.value}",
            )
        ],
    }


# =========================================================
# CLARIFICATION NODE
# =========================================================

def ask_clarification_node(state: AgentState) -> dict[str, Any]:
    """
    Request additional information safely.
    """

    query = state.get("query", "")

    if "order" in query.lower():
        question = "Please provide the order ID so I can continue."

    elif "account" in query.lower():
        question = "Please provide the account identifier or email address."

    else:
        question = "Can you provide more details about the request?"

    return {
        "pending_question": question,
        "final_answer": question,
        "messages": [
            create_message("assistant", question),
        ],
        "events": [
            make_event(
                "clarify",
                "completed",
                "clarification requested",
            )
        ],
    }


# =========================================================
# TOOL NODE
# =========================================================

def tool_node(state: AgentState) -> dict[str, Any]:
    """
    Simulated tool/API execution.
    """

    attempt = int(state.get("attempt", 0))
    scenario_id = state.get("scenario_id", "unknown")
    route = state.get("route")

    if route == Route.ERROR.value and attempt < 2:
        result = {
            "status": "ERROR",
            "attempt": attempt,
            "scenario": scenario_id,
            "message": "Transient service failure",
        }

    else:
        result = {
            "status": "SUCCESS",
            "attempt": attempt,
            "scenario": scenario_id,
            "data": f"mock-tool-result-{scenario_id}",
        }

    return {
        "tool_results": [result],
        "events": [
            make_event(
                "tool",
                "completed",
                f"tool executed attempt={attempt}",
                attempt=attempt,
            )
        ],
    }


# =========================================================
# RISKY ACTION NODE
# =========================================================

def risky_action_node(state: AgentState) -> dict[str, Any]:
    """
    Prepare high-risk actions for approval.
    """

    query = state.get("query", "")

    proposed_action = {
        "action": query,
        "risk_level": "high",
        "requires_approval": True,
        "reason": "Destructive or externally impactful action detected",
    }

    return {
        "proposed_action": proposed_action,
        "events": [
            make_event(
                "risky_action",
                "pending_approval",
                "approval required before execution",
            )
        ],
    }


# =========================================================
# APPROVAL NODE
# =========================================================

def approval_node(state: AgentState) -> dict[str, Any]:
    """
    Human-in-the-loop approval stage.
    """

    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":

        from langgraph.types import interrupt

        value = interrupt(
            {
                "proposed_action": state.get("proposed_action"),
                "risk_level": state.get("risk_level"),
            }
        )

        if isinstance(value, dict):
            decision = ApprovalDecision(**value)

        else:
            decision = ApprovalDecision(
                approved=bool(value),
            )

    else:
        decision = ApprovalDecision(
            approved=True,
            comment="mock approval for local execution",
        )

    return {
        "approval": decision.model_dump(),
        "events": [
            make_event(
                "approval",
                "completed",
                f"approved={decision.approved}",
            )
        ],
    }


# =========================================================
# RETRY NODE
# =========================================================

def retry_or_fallback_node(state: AgentState) -> dict[str, Any]:
    """
    Handle bounded retries with metadata.
    """

    current_attempt = int(state.get("attempt", 0))
    next_attempt = current_attempt + 1

    backoff_seconds = min(2 ** current_attempt, 8)

    # simulated backoff for demo
    time.sleep(0.1)

    error_message = (
        f"retry attempt={next_attempt} "
        f"backoff={backoff_seconds}s"
    )

    return {
        "attempt": next_attempt,
        "errors": [error_message],
        "events": [
            make_event(
                "retry",
                "completed",
                error_message,
                attempt=next_attempt,
            )
        ],
    }


# =========================================================
# EVALUATION NODE
# =========================================================

def evaluate_node(state: AgentState) -> dict[str, Any]:
    """
    Validate latest tool execution result.
    """

    tool_results = state.get("tool_results", [])

    if not tool_results:
        return {
            "evaluation_result": "needs_retry",
            "events": [
                make_event(
                    "evaluate",
                    "completed",
                    "missing tool result",
                )
            ],
        }

    latest = tool_results[-1]

    if latest.get("status") == "ERROR":
        return {
            "evaluation_result": "needs_retry",
            "events": [
                make_event(
                    "evaluate",
                    "completed",
                    "tool execution failed",
                )
            ],
        }

    return {
        "evaluation_result": "success",
        "events": [
            make_event(
                "evaluate",
                "completed",
                "tool execution successful",
            )
        ],
    }


# =========================================================
# ANSWER NODE
# =========================================================

def answer_node(state: AgentState) -> dict[str, Any]:
    """
    Generate final grounded response.
    """

    tool_results = state.get("tool_results", [])

    if tool_results:
        latest = tool_results[-1]

        answer = (
            f"Request completed successfully. "
            f"Result: {latest.get('data', 'No data returned')}."
        )

    else:
        answer = (
            "Request processed successfully without tool execution."
        )

    return {
        "final_answer": answer,
        "messages": [
            create_message("assistant", answer),
        ],
        "events": [
            make_event(
                "answer",
                "completed",
                "final response generated",
            )
        ],
    }


# =========================================================
# DEAD LETTER NODE
# =========================================================

def dead_letter_node(state: AgentState) -> dict[str, Any]:
    """
    Handle unrecoverable workflow failures.
    """

    attempt = state.get("attempt", 0)

    answer = (
        "The request could not be completed after "
        f"{attempt} retry attempts. "
        "The issue has been escalated for manual review."
    )

    return {
        "final_answer": answer,
        "messages": [
            create_message("system", answer),
        ],
        "events": [
            make_event(
                "dead_letter",
                "completed",
                f"max retries exceeded attempt={attempt}",
            )
        ],
    }


# =========================================================
# FINALIZE NODE
# =========================================================

def finalize_node(state: AgentState) -> dict[str, Any]:
    """
    Final workflow cleanup and audit logging.
    """

    return {
        "events": [
            make_event(
                "finalize",
                "completed",
                "workflow execution finished",
            )
        ]
    }