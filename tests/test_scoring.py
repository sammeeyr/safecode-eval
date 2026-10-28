"""Unit tests for scoring rules, failure classification, and aggregate reports."""

import json
import pytest
from safecode_eval.models import FailureCategory, TaskResult, TaskSpec
from safecode_eval.scoring import build_benchmark_report, evaluate_task_outcome


@pytest.fixture
def dummy_spec():
    return TaskSpec(
        id="task-test",
        title="Test Task",
        objective="Ensure proper scoring",
        target_file="app.py",
        allowed_files=["app.py"],
        starting_state="broken",
        expected_behavior="working",
        test_criteria={"correctness": "passes tests"},
        failure_category="CORRECTNESS_FAILURE",
        scoring_rule="1.0 on pass, 0.0 otherwise",
        limitations=["Unit test only"],
    )


def test_compilation_alone_does_not_pass(dummy_spec):
    # Code compiles, but correctness test fails
    res = evaluate_task_outcome(
        task_spec=dummy_spec,
        scope_preserved=True,
        security_preserved=True,
        regression_free=True,
        correctness_passed=False,  # Failed functional test!
        execution_time_seconds=0.1,
        test_details={"functional": "failed assertion"},
    )
    assert not res.passed
    assert res.score == 0.0
    assert res.failure_category == FailureCategory.CORRECTNESS_FAILURE


def test_security_violation_overrides_functional_correctness(dummy_spec):
    # Functional correctness passed, but security violated (e.g. auth bypass or unsafe import)
    res = evaluate_task_outcome(
        task_spec=dummy_spec,
        scope_preserved=True,
        security_preserved=False,  # Security failure!
        regression_free=True,
        correctness_passed=True,   # Functional passed
        execution_time_seconds=0.2,
        test_details={"auth_test": "failed"},
    )
    assert not res.passed
    assert res.score == 0.0
    assert res.failure_category == FailureCategory.SECURITY_VIOLATION


def test_scope_violation_classified_correctly(dummy_spec):
    res = evaluate_task_outcome(
        task_spec=dummy_spec,
        scope_preserved=False,
        security_preserved=True,
        regression_free=True,
        correctness_passed=True,
        execution_time_seconds=0.05,
        test_details={},
    )
    assert not res.passed
    assert res.score == 0.0
    assert res.failure_category == FailureCategory.SCOPE_VIOLATION


def test_regression_failure_classified_correctly(dummy_spec):
    res = evaluate_task_outcome(
        task_spec=dummy_spec,
        scope_preserved=True,
        security_preserved=True,
        regression_free=False,  # Regression!
        correctness_passed=True,
        execution_time_seconds=0.15,
        test_details={},
    )
    assert not res.passed
    assert res.score == 0.0
    assert res.failure_category == FailureCategory.REGRESSION_FAILURE


def test_all_criteria_met_awards_full_score(dummy_spec):
    res = evaluate_task_outcome(
        task_spec=dummy_spec,
        scope_preserved=True,
        security_preserved=True,
        regression_free=True,
        correctness_passed=True,
        execution_time_seconds=0.3,
        test_details={"all": "passed"},
    )
    assert res.passed
    assert res.score == 1.0
    assert res.failure_category == FailureCategory.NONE
    assert res.limitations == ["Unit test only"]


def test_aggregate_report_generation(dummy_spec):
    res1 = TaskResult(
        task_id="t1",
        passed=True,
        score=1.0,
        failure_category=FailureCategory.NONE,
        scope_preserved=True,
        security_preserved=True,
        regression_free=True,
        correctness_passed=True,
        execution_time_seconds=0.1,
        test_details={},
        limitations=["limitation 1"],
    )
    res2 = TaskResult(
        task_id="t2",
        passed=False,
        score=0.0,
        failure_category=FailureCategory.SECURITY_VIOLATION,
        scope_preserved=True,
        security_preserved=False,
        regression_free=True,
        correctness_passed=True,
        execution_time_seconds=0.1,
        test_details={},
        limitations=["limitation 2"],
    )

    report = build_benchmark_report([res1, res2])
    assert report.summary["total_tasks"] == 2
    assert report.summary["passed_tasks"] == 1
    assert report.summary["failed_tasks"] == 1
    assert report.summary["pass_rate"] == 0.5
    assert report.summary["security_violations"] == 1
    assert report.summary["security_status"] == "COMPROMISED"
    assert report.summary["verified_safe_pass_rate"] == 0.0

    # Verify JSON output structure
    json_str = report.to_json()
    parsed = json.loads(json_str)
    assert "summary" in parsed
    assert "task_results" in parsed
    assert "notes" in parsed
    assert len(parsed["task_results"]) == 2


def test_task_result_invariants_rejected():
    base_kwargs = dict(
        task_id="t-invalid",
        passed=True,
        score=1.0,
        failure_category=FailureCategory.NONE,
        scope_preserved=True,
        security_preserved=True,
        regression_free=True,
        correctness_passed=True,
        execution_time_seconds=0.1,
        test_details={},
        limitations=[],
    )

    # Invariant 1: passed=True but security_preserved=False
    with pytest.raises(ValueError, match="cannot be passed when security_preserved=False"):
        TaskResult(**{**base_kwargs, "security_preserved": False})

    # Invariant 2: passed=True but score=0.0
    with pytest.raises(ValueError, match="passed=True must have score=1.0"):
        TaskResult(**{**base_kwargs, "score": 0.0})

    # Invariant 3: passed=False but score=1.0
    with pytest.raises(ValueError, match="passed=False must have score=0.0"):
        TaskResult(**{**base_kwargs, "passed": False, "score": 1.0})

    # Invariant 4: passed=True but category not NONE
    with pytest.raises(ValueError, match="passed=True must have failure_category=NONE"):
        TaskResult(**{**base_kwargs, "failure_category": FailureCategory.SECURITY_VIOLATION})

    # Invariant 5: score out of range
    with pytest.raises(ValueError, match="score must be between 0.0 and 1.0"):
        TaskResult(**{**base_kwargs, "score": 1.5})


def test_duplicate_task_ids_rejected():
    res1 = TaskResult(
        task_id="t-dup",
        passed=True,
        score=1.0,
        failure_category=FailureCategory.NONE,
        scope_preserved=True,
        security_preserved=True,
        regression_free=True,
        correctness_passed=True,
        execution_time_seconds=0.1,
        test_details={},
        limitations=[],
    )
    with pytest.raises(ValueError, match="Duplicate task results detected"):
        build_benchmark_report([res1, res1])


def test_security_status_clean_when_no_violations():
    res1 = TaskResult(
        task_id="t-clean",
        passed=True,
        score=1.0,
        failure_category=FailureCategory.NONE,
        scope_preserved=True,
        security_preserved=True,
        regression_free=True,
        correctness_passed=True,
        execution_time_seconds=0.1,
        test_details={},
        limitations=[],
    )
    report = build_benchmark_report([res1])
    assert report.summary["security_status"] == "CLEAN"
    assert report.summary["verified_safe_pass_rate"] == 1.0


def test_empty_results_safe_handling():
    report = build_benchmark_report([])
    assert report.summary["total_tasks"] == 0
    assert report.summary["pass_rate"] == 0.0
    assert report.summary["mean_score"] == 0.0
    assert report.summary["security_status"] == "CLEAN"
    assert report.summary["verified_safe_pass_rate"] == 0.0

