"""State schema definitions for the Day 08 LangGraph workflow.

This module defines:
- workflow routes,
- audit events,
- approval decisions,
- graph state schema,
- scenario schema,
- helper factories.

Design goals:
- serializable state,
- append-only auditability,
- retry-safe execution,
- deterministic workflow behavior,
- production-ready extensibility.
"""

from __future__ import annotations

from enum import StrEnum
from operator import add
from typing import Annotated, Any, TypedDict

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


# =========================================================
# ROUTE ENUM
# =========================================================

class Route(StrEnum):
    """
    Workflow routing categories.
    """

    SIMPLE = "simple"

    TOOL = "tool"

    MISSING_INFO = "missing_info"

    RISKY = "risky"

    ERROR = "error"

    DEAD_LETTER = "dead_letter"

    DONE = "done"


# =========================================================
# AUDIT EVENT MODEL
# =========================================================

class LabEvent(BaseModel):
    """
    Append-only workflow audit event.

    Used for:
    - debugging,
    - observability,
    - grading,
    - tracing,
    - metrics collection.
    """

    node: str

    event_type: str

    message: str

    latency_ms: int = 0

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


# =========================================================
# APPROVAL DECISION MODEL
# =========================================================

class ApprovalDecision(BaseModel):
    """
    Human approval decision payload.
    """

    approved: bool = False

    reviewer: str = "mock-reviewer"

    comment: str = ""

    edited_action: str | None = None


# =========================================================
# WORKFLOW STATE
# =========================================================

class AgentState(TypedDict, total=False):
    """
    Serializable LangGraph workflow state.

    Rules:
    - append-only collections preserve audit history
    - scalar values overwrite latest execution state
    - all fields must remain serializable
    """

    # -----------------------------------------------------
    # EXECUTION IDENTIFIERS
    # -----------------------------------------------------

    thread_id: str

    scenario_id: str

    session_id: str

    # -----------------------------------------------------
    # USER INPUT
    # -----------------------------------------------------

    query: str

    normalized_query: str

    # -----------------------------------------------------
    # ROUTING / EXECUTION
    # -----------------------------------------------------

    route: str

    risk_level: str

    evaluation_result: str | None

    # -----------------------------------------------------
    # RETRY MANAGEMENT
    # -----------------------------------------------------

    attempt: int

    max_attempts: int

    retry_backoff_seconds: int

    # -----------------------------------------------------
    # RESPONSES
    # -----------------------------------------------------

    final_answer: str | None

    pending_question: str | None

    # -----------------------------------------------------
    # APPROVAL / RISK
    # -----------------------------------------------------

    proposed_action: dict[str, Any] | None

    approval: dict[str, Any] | None

    # -----------------------------------------------------
    # METADATA
    # -----------------------------------------------------

    metadata: dict[str, Any]

    # -----------------------------------------------------
    # APPEND-ONLY AUDIT FIELDS
    # -----------------------------------------------------

    messages: Annotated[list[str], add]

    tool_results: Annotated[
        list[dict[str, Any]],
        add,
    ]

    errors: Annotated[list[str], add]

    events: Annotated[
        list[dict[str, Any]],
        add,
    ]


# =========================================================
# SCENARIO MODEL
# =========================================================

class Scenario(BaseModel):
    """
    Scenario configuration for workflow testing.
    """

    id: str

    query: str

    expected_route: Route

    requires_approval: bool = False

    should_retry: bool = False

    max_attempts: int = 3

    tags: list[str] = Field(
        default_factory=list
    )

    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

    @field_validator("query")
    @classmethod
    def query_must_not_be_empty(
        cls,
        value: str,
    ) -> str:
        """
        Ensure scenario query is valid.
        """

        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                "query must not be empty"
            )

        return cleaned

    @field_validator("max_attempts")
    @classmethod
    def max_attempts_must_be_positive(
        cls,
        value: int,
    ) -> int:
        """
        Validate retry limit.
        """

        if value < 1:
            raise ValueError(
                "max_attempts must be >= 1"
            )

        return value


# =========================================================
# INITIAL STATE FACTORY
# =========================================================

def initial_state(
    scenario: Scenario,
) -> AgentState:
    """
    Create initial serializable workflow state.
    """

    return {
        # -------------------------------------------------
        # IDENTIFIERS
        # -------------------------------------------------

        "thread_id": f"thread-{scenario.id}",

        "scenario_id": scenario.id,

        "session_id": f"session-{scenario.id}",

        # -------------------------------------------------
        # INPUT
        # -------------------------------------------------

        "query": scenario.query,

        "normalized_query": scenario.query.strip(),

        # -------------------------------------------------
        # ROUTING
        # -------------------------------------------------

        "route": "",

        "risk_level": "unknown",

        "evaluation_result": None,

        # -------------------------------------------------
        # RETRIES
        # -------------------------------------------------

        "attempt": 0,

        "max_attempts": scenario.max_attempts,

        "retry_backoff_seconds": 0,

        # -------------------------------------------------
        # RESPONSES
        # -------------------------------------------------

        "final_answer": None,

        "pending_question": None,

        # -------------------------------------------------
        # APPROVAL
        # -------------------------------------------------

        "proposed_action": None,

        "approval": None,

        # -------------------------------------------------
        # METADATA
        # -------------------------------------------------

        "metadata": {
            "requires_approval": scenario.requires_approval,
            "should_retry": scenario.should_retry,
            "tags": scenario.tags,
        },

        # -------------------------------------------------
        # APPEND-ONLY FIELDS
        # -------------------------------------------------

        "messages": [],

        "tool_results": [],

        "errors": [],

        "events": [],
    }


# =========================================================
# EVENT FACTORY
# =========================================================

def make_event(
    node: str,
    event_type: str,
    message: str,
    **metadata: Any,
) -> dict[str, Any]:
    """
    Create normalized audit event payload.
    """

    return LabEvent(
        node=node,
        event_type=event_type,
        message=message,
        metadata=metadata,
    ).model_dump()