"""Checkpoint persistence adapters for LangGraph workflows.

Supports:
- Memory checkpointing (default)
- SQLite persistence
- PostgreSQL persistence
- No persistence mode

Design goals:
- Import-safe
- Clear runtime errors
- Minimal infrastructure setup
- Production-ready extension points
"""

from __future__ import annotations

from typing import Any


# =========================================================
# CHECKPOINTER FACTORY
# =========================================================

def build_checkpointer(
    kind: str = "memory",
    database_url: str | None = None,
) -> Any | None:
    """
    Build and return a LangGraph checkpointer.

    Parameters
    ----------
    kind : str
        Checkpointer backend type.

        Supported values:
        - "memory"
        - "sqlite"
        - "postgres"
        - "none"

    database_url : str | None
        Optional database connection string.

    Returns
    -------
    Any | None
        Configured LangGraph checkpointer instance.

    Raises
    ------
    RuntimeError
        If required persistence package is missing.

    ValueError
        If unsupported checkpointer type is provided.
    """

    normalized_kind = kind.strip().lower()

    # =====================================================
    # NO PERSISTENCE
    # =====================================================

    if normalized_kind == "none":
        return None

    # =====================================================
    # IN-MEMORY CHECKPOINTING
    # =====================================================

    if normalized_kind == "memory":

        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()

    # =====================================================
    # SQLITE CHECKPOINTING
    # =====================================================

    if normalized_kind == "sqlite":

        try:
            from langgraph.checkpoint.sqlite import SqliteSaver

        except ImportError as exc:
            raise RuntimeError(
                "SQLite checkpoint support requires:\n"
                "pip install langgraph-checkpoint-sqlite"
            ) from exc

        connection_string = database_url or "checkpoints.db"

        return SqliteSaver.from_conn_string(
            connection_string,
        )

    # =====================================================
    # POSTGRES CHECKPOINTING
    # =====================================================

    if normalized_kind == "postgres":

        try:
            from langgraph.checkpoint.postgres import PostgresSaver

        except ImportError as exc:
            raise RuntimeError(
                "Postgres checkpoint support requires:\n"
                "pip install langgraph-checkpoint-postgres"
            ) from exc

        if not database_url:
            raise ValueError(
                "Postgres checkpointer requires a database_url."
            )

        return PostgresSaver.from_conn_string(
            database_url,
        )

    # =====================================================
    # UNSUPPORTED TYPE
    # =====================================================

    supported = [
        "memory",
        "sqlite",
        "postgres",
        "none",
    ]

    raise ValueError(
        f"Unknown checkpointer kind: '{kind}'. "
        f"Supported types: {supported}"
    )