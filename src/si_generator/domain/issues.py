from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def count_issues(issues: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"info": 0, "warning": 0, "error": 0}
    for issue in issues:
        severity = str(issue.get("severity", "warning")).lower()
        if severity not in counts:
            severity = "warning"
        counts[severity] += 1
    return counts


def generation_status(issue_counts: Mapping[str, int]) -> str:
    if issue_counts.get("error", 0):
        return "failed"
    if issue_counts.get("warning", 0):
        return "completed_with_warnings"
    return "completed"
