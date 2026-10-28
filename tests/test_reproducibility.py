"""Reproducibility verification tests running benchmark repeatedly."""

from pathlib import Path
import pytest

from safecode_eval.runner import run_benchmark


@pytest.fixture
def tasks_dir() -> Path:
    return Path(__file__).parent.parent / "tasks"


def test_evaluator_runs_are_strictly_reproducible(tasks_dir: Path):
    # Run 1
    report_1 = run_benchmark(tasks_dir=tasks_dir, patch_type="good")

    # Run 2
    report_2 = run_benchmark(tasks_dir=tasks_dir, patch_type="good")

    # Summary metrics must match exactly
    assert report_1.summary["total_tasks"] == report_2.summary["total_tasks"]
    assert report_1.summary["passed_tasks"] == report_2.summary["passed_tasks"]
    assert report_1.summary["failed_tasks"] == report_2.summary["failed_tasks"]
    assert report_1.summary["pass_rate"] == report_2.summary["pass_rate"]
    assert report_1.summary["mean_score"] == report_2.summary["mean_score"]
    assert report_1.summary["failure_breakdown"] == report_2.summary["failure_breakdown"]

    # Individual task results must match exactly
    assert len(report_1.task_results) == len(report_2.task_results)
    for res1, res2 in zip(report_1.task_results, report_2.task_results):
        assert res1["task_id"] == res2["task_id"]
        assert res1["passed"] == res2["passed"]
        assert res1["score"] == res2["score"]
        assert res1["failure_category"] == res2["failure_category"]
        assert res1["scope_preserved"] == res2["scope_preserved"]
        assert res1["security_preserved"] == res2["security_preserved"]
        assert res1["regression_free"] == res2["regression_free"]
        assert res1["correctness_passed"] == res2["correctness_passed"]
        assert res1["limitations"] == res2["limitations"]

