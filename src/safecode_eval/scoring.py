"""Scoring logic, failure classification, and aggregate reporting."""

from __future__ import annotations

import datetime
import sys
from typing import Any, Dict, List, Optional, Set

from safecode_eval.models import BenchmarkReport, FailureCategory, TaskResult, TaskSpec


def evaluate_task_outcome(
    task_spec: TaskSpec,
    scope_preserved: bool,
    security_preserved: bool,
    regression_free: bool,
    correctness_passed: bool,
    execution_time_seconds: float,
    test_details: Dict[str, Any],
    error_message: Optional[str] = None,
    failure_category_override: Optional[FailureCategory] = None,
) -> TaskResult:
    """Evaluates task outcome strictly separating functional correctness from security violations.

    A passing score is NEVER awarded merely because code parses or compiles.
    All dimensions (scope, security, regression-free, correctness) must hold.
    """
    category = FailureCategory.NONE

    if failure_category_override is not None:
        category = failure_category_override
    elif not scope_preserved:
        category = FailureCategory.SCOPE_VIOLATION
    elif not security_preserved:
        category = FailureCategory.SECURITY_VIOLATION
    elif not regression_free:
        category = FailureCategory.REGRESSION_FAILURE
    elif not correctness_passed:
        category = FailureCategory.CORRECTNESS_FAILURE

    # Code compiles is NOT sufficient: all criteria must pass
    all_criteria_met = (
        scope_preserved
        and security_preserved
        and regression_free
        and correctness_passed
        and category == FailureCategory.NONE
    )

    passed = all_criteria_met
    score = 1.0 if passed else 0.0

    return TaskResult(
        task_id=task_spec.id,
        passed=passed,
        score=score,
        failure_category=category,
        scope_preserved=scope_preserved,
        security_preserved=security_preserved,
        regression_free=regression_free,
        correctness_passed=correctness_passed,
        execution_time_seconds=round(execution_time_seconds, 4),
        test_details=test_details,
        limitations=task_spec.limitations,
        error_message=error_message,
    )


def build_benchmark_report(
    results: List[TaskResult],
    benchmark_version: str = "0.1.0",
    platform_info: Optional[str] = None,
    python_version: Optional[str] = None,
    extra_notes: Optional[List[str]] = None,
) -> BenchmarkReport:
    """Aggregates individual task results into a comprehensive, deterministic report."""
    # Validate unique task IDs to prevent double-counting
    seen_ids: Set[str] = set()
    duplicates: List[str] = []
    for r in results:
        if r.task_id in seen_ids:
            duplicates.append(r.task_id)
        seen_ids.add(r.task_id)
    if duplicates:
        raise ValueError(f"Duplicate task results detected in evaluation: {sorted(set(duplicates))}")

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    failure_counts: Dict[str, int] = {cat.value: 0 for cat in FailureCategory}
    for r in results:
        failure_counts[r.failure_category.value] += 1

    pass_rate = round(passed / total, 4) if total > 0 else 0.0
    mean_score = round(sum(r.score for r in results) / total, 4) if total > 0 else 0.0

    sec_violations = failure_counts[FailureCategory.SECURITY_VIOLATION.value]
    security_status = "CLEAN" if sec_violations == 0 else "COMPROMISED"
    verified_safe_pass_rate = pass_rate if sec_violations == 0 else 0.0

    summary = {
        "total_tasks": total,
        "passed_tasks": passed,
        "failed_tasks": failed,
        "pass_rate": pass_rate,
        "mean_score": mean_score,
        "security_status": security_status,
        "verified_safe_pass_rate": verified_safe_pass_rate,
        "scope_violations": failure_counts[FailureCategory.SCOPE_VIOLATION.value],
        "security_violations": sec_violations,
        "regression_failures": failure_counts[FailureCategory.REGRESSION_FAILURE.value],
        "correctness_failures": failure_counts[FailureCategory.CORRECTNESS_FAILURE.value],
        "syntax_errors": failure_counts[FailureCategory.PARSE_OR_SYNTAX_ERROR.value],
        "timeout_errors": failure_counts[FailureCategory.TIMEOUT_ERROR.value],
        "specification_errors": failure_counts[FailureCategory.SPECIFICATION_ERROR.value],
        "failure_breakdown": failure_counts,
    }

    notes = [
        "Evaluated using deterministic, independently authored tests.",
        "Functional correctness is evaluated separately from security and scope constraints.",
        "Code compilation or successful parsing alone does not grant a passing score.",
        "No AI model claim is made for test grading authority.",
    ]
    if extra_notes:
        notes.extend(extra_notes)

    return BenchmarkReport(
        benchmark_version=benchmark_version,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        platform=platform_info or sys.platform,
        python_version=python_version or sys.version.split()[0],
        summary=summary,
        task_results=[r.to_dict() for r in results],
        notes=notes,
    )

