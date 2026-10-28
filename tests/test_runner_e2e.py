"""End-to-end evaluator tests verifying known-good and deliberately bad patches."""

from pathlib import Path
import pytest

from safecode_eval.models import FailureCategory
from safecode_eval.runner import evaluate_task_patch, run_benchmark


@pytest.fixture
def tasks_dir() -> Path:
    return Path(__file__).parent.parent / "tasks"


def test_known_good_patches_all_pass(tasks_dir: Path):
    report = run_benchmark(tasks_dir=tasks_dir, patch_type="good")

    assert report.summary["total_tasks"] == 3
    assert report.summary["passed_tasks"] == 3
    assert report.summary["failed_tasks"] == 0
    assert report.summary["pass_rate"] == 1.0
    assert report.summary["mean_score"] == 1.0

    for tr in report.task_results:
        assert tr["passed"] is True
        assert tr["score"] == 1.0
        assert tr["failure_category"] == FailureCategory.NONE.value
        assert tr["scope_preserved"] is True
        assert tr["security_preserved"] is True
        assert tr["regression_free"] is True
        assert tr["correctness_passed"] is True
        assert len(tr["limitations"]) > 0


def test_task_01_bad_incorrect_patch_fails_correctness(tasks_dir: Path):
    task_dir = tasks_dir / "task_01_correctness"
    patch_path = task_dir / "patches" / "bad_incorrect.patch"
    patch_text = patch_path.read_text(encoding="utf-8")

    result = evaluate_task_patch(task_dir, patch_text)
    assert not result.passed
    assert result.score == 0.0
    assert result.failure_category == FailureCategory.CORRECTNESS_FAILURE
    assert result.regression_free is True  # Regression didn't fail
    assert result.correctness_passed is False  # Functional test failed!


def test_task_02_bad_regression_patch_fails_regression(tasks_dir: Path):
    task_dir = tasks_dir / "task_02_regression"
    patch_path = task_dir / "patches" / "bad_regression.patch"
    patch_text = patch_path.read_text(encoding="utf-8")

    result = evaluate_task_patch(task_dir, patch_text)
    assert not result.passed
    assert result.score == 0.0
    assert result.failure_category == FailureCategory.REGRESSION_FAILURE
    assert result.regression_free is False  # Regression suite broke!
    assert result.correctness_passed is True  # Functional query param logic worked!


def test_task_03_bad_security_patch_fails_security(tasks_dir: Path):
    task_dir = tasks_dir / "task_03_authorization"
    patch_path = task_dir / "patches" / "bad_security.patch"
    patch_text = patch_path.read_text(encoding="utf-8")

    result = evaluate_task_patch(task_dir, patch_text)
    assert not result.passed
    assert result.score == 0.0
    assert result.failure_category == FailureCategory.SECURITY_VIOLATION
    assert result.security_preserved is False  # Unauthorized access permitted!


def test_task_03_bad_scope_patch_fails_scope(tasks_dir: Path):
    task_dir = tasks_dir / "task_03_authorization"
    patch_path = task_dir / "patches" / "bad_scope.patch"
    patch_text = patch_path.read_text(encoding="utf-8")

    result = evaluate_task_patch(task_dir, patch_text)
    assert not result.passed
    assert result.score == 0.0
    assert result.failure_category == FailureCategory.SCOPE_VIOLATION
    assert result.scope_preserved is False


def test_task_03_bad_ast_safety_patch_blocks_execution(tasks_dir: Path):
    task_dir = tasks_dir / "task_03_authorization"
    patch_path = task_dir / "patches" / "bad_ast_safety.patch"
    patch_text = patch_path.read_text(encoding="utf-8")

    result = evaluate_task_patch(task_dir, patch_text)
    assert not result.passed
    assert result.score == 0.0
    assert result.failure_category == FailureCategory.SECURITY_VIOLATION
    assert result.security_preserved is False
    assert "AST Safety violation detected" in (result.error_message or "")

