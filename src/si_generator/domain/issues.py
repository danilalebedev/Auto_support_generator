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


def issue_code_counts(issues: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in issues:
        code = str(issue.get("code") or "UNKNOWN").strip() or "UNKNOWN"
        counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def generation_status(issue_counts: Mapping[str, int]) -> str:
    if issue_counts.get("error", 0):
        return "failed"
    if issue_counts.get("warning", 0):
        return "completed_with_warnings"
    return "completed"


def issues_by_compound(issues: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for issue in issues:
        compound_id = str(issue.get("compound_id") or "").strip()
        if not compound_id:
            continue
        grouped.setdefault(compound_id, []).append(dict(issue))
    return grouped


def compound_issue_counts(issues: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return {compound_id: len(items) for compound_id, items in issues_by_compound(issues).items()}
