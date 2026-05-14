"""Automated report generation utilities.

This module generates a structured Markdown lab report
from workflow execution metrics.

Features:
- Clean Markdown formatting
- Metrics summary
- Scenario statistics
- Architecture overview
- Failure analysis
- Improvement roadmap
- File export support
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .metrics import MetricsReport


# =========================================================
# REPORT TEMPLATE
# =========================================================

def render_report(metrics: MetricsReport) -> str:
    """
    Render a complete Markdown lab report.

    Parameters
    ----------
    metrics : MetricsReport
        Aggregated workflow metrics.

    Returns
    -------
    str
        Markdown report content.
    """

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""# Day 08 Lab Report

## 1. Student Information

- **Name:** Nguyen Tien Dat
- **Generated At:** {generated_at}

---

# 2. Workflow Overview

This project implements a LangGraph-based workflow orchestration system with:

- dynamic request classification,
- tool execution,
- retry and recovery handling,
- human-in-the-loop approval,
- persistence and checkpointing,
- and structured audit logging.

The workflow is designed with explicit node boundaries to ensure:

- modularity,
- observability,
- fault tolerance,
- and safe execution control.

---

# 3. Architecture Summary

## Main Workflow Stages

1. **Intake**
   - Normalize incoming requests
   - Validate input
   - Initialize audit events

2. **Classification**
   - Route requests into:
     - simple
     - tool
     - risky
     - missing_info
     - error

3. **Tool Execution**
   - Execute simulated tools/APIs
   - Return structured results

4. **Evaluation**
   - Validate tool outputs
   - Decide success or retry

5. **Retry System**
   - Bounded retry loop
   - Exponential backoff support
   - Dead-letter escalation

6. **Risky Action Approval**
   - Human approval before destructive actions
   - Interrupt/resume workflow support

7. **Finalization**
   - Persist metrics and audit logs
   - Safely terminate execution

---

# 4. Metrics Summary

| Metric | Value |
|---|---:|
| Total Scenarios | {metrics.total_scenarios} |
| Success Rate | {metrics.success_rate:.2%} |
| Average Nodes Visited | {metrics.avg_nodes_visited:.2f} |
| Total Retries | {metrics.total_retries} |
| Total Interrupts | {metrics.total_interrupts} |
| Resume Success | {metrics.resume_success} |

---

# 5. Execution Analysis

## Retry Behavior

The retry mechanism handles transient failures safely by:

- incrementing retry counters,
- applying bounded retry logic,
- supporting exponential backoff,
- escalating unrecoverable failures.

If retry attempts exceed the configured threshold,
the workflow transitions into the `dead_letter` stage.

---

## Risk Management

Risk-sensitive requests such as:

- refunds,
- account deletion,
- subscription cancellation,
- access revocation,

require approval before execution.

This prevents unsafe or destructive operations from running automatically.

---

## Clarification Handling

Incomplete or ambiguous requests are routed into
a clarification flow instead of allowing hallucinated responses.

Example:
- Missing order IDs
- Missing account identifiers
- Vague support issues

---

# 6. Persistence and Recovery

The workflow supports multiple checkpoint backends:

| Backend | Status |
|---|---|
| MemorySaver | Supported |
| SQLite | Supported |
| PostgreSQL | Supported |

Checkpointing enables:

- workflow recovery,
- replay,
- interrupt/resume execution,
- persistent audit trails.

---

# 7. Failure Modes

## Recoverable Failures

Handled using retry logic:
- timeout
- temporary service failure
- gateway issues
- transient API errors

## Non-Recoverable Failures

Escalated into dead-letter handling:
- retry exhaustion
- invalid execution states
- unrecoverable system errors

---

# 8. Improvement Plan

Future improvements may include:

1. Real external API integrations
2. Typed structured tool outputs
3. Distributed checkpoint persistence
4. Reviewer dashboard UI
5. Advanced policy validation
6. LLM-based evaluation scoring
7. Observability dashboards and tracing
8. Streaming execution support

---

# 9. Conclusion

This lab demonstrates a production-oriented LangGraph workflow
with:

- deterministic routing,
- bounded retries,
- approval gates,
- fault recovery,
- persistence,
- and auditability.

The architecture is modular, extensible, and suitable
for scalable AI workflow orchestration systems.
"""


# =========================================================
# REPORT WRITER
# =========================================================

def write_report(
    metrics: MetricsReport,
    output_path: str | Path,
) -> None:
    """
    Generate and save the Markdown report.

    Parameters
    ----------
    metrics : MetricsReport
        Workflow execution metrics.

    output_path : str | Path
        Destination Markdown file path.
    """

    path = Path(output_path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_content = render_report(metrics)

    path.write_text(
        report_content,
        encoding="utf-8",
    )