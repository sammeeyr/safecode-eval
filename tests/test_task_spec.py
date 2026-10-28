"""Tests for task specification loading, schema validation, and malformation detection."""

import json
from pathlib import Path
import pytest

from safecode_eval.models import SpecificationError, TaskSpec
from safecode_eval.runner import load_task_spec, discover_tasks


def test_valid_task_specs_load(tmp_path: Path):
    spec_data = {
        "id": "sample-task",
        "title": "Sample Task Title",
        "objective": "Test objective",
        "target_file": "module.py",
        "allowed_files": ["module.py"],
        "starting_state": "Buggy state",
        "expected_behavior": "Fixed state",
        "test_criteria": {"functional": "Works properly"},
        "failure_category": "CORRECTNESS_FAILURE",
        "scoring_rule": "Binary 1.0 / 0.0",
        "limitations": ["Limited to tests"],
    }
    task_dir = tmp_path / "sample_task"
    task_dir.mkdir()
    (task_dir / "task.json").write_text(json.dumps(spec_data), encoding="utf-8")

    workspace = task_dir / "workspace"
    workspace.mkdir()
    (workspace / "module.py").write_text("# code", encoding="utf-8")

    tests = task_dir / "tests"
    tests.mkdir()

    spec = load_task_spec(task_dir)
    assert spec.id == "sample-task"
    assert spec.target_file == "module.py"
    assert spec.allowed_files == ["module.py"]


def test_missing_task_json_raises_specification_error(tmp_path: Path):
    empty_dir = tmp_path / "empty_task"
    empty_dir.mkdir()
    with pytest.raises(SpecificationError, match="Missing task.json"):
        load_task_spec(empty_dir)


def test_malformed_json_raises_specification_error(tmp_path: Path):
    task_dir = tmp_path / "broken_json"
    task_dir.mkdir()
    (task_dir / "task.json").write_text("{ unquoted_key: invalid }", encoding="utf-8")
    with pytest.raises(SpecificationError, match="Malformed JSON"):
        load_task_spec(task_dir)


def test_missing_required_fields_detected(tmp_path: Path):
    task_dir = tmp_path / "incomplete_task"
    task_dir.mkdir()
    # Missing 'failure_category' and 'scoring_rule'
    bad_data = {
        "id": "incomplete-task",
        "title": "Incomplete",
        "objective": "Objective",
        "target_file": "module.py",
        "allowed_files": ["module.py"],
        "starting_state": "State",
        "expected_behavior": "Expected",
        "test_criteria": {"c": "rule"},
    }
    (task_dir / "task.json").write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(SpecificationError, match="missing required fields"):
        load_task_spec(task_dir)


def test_target_file_not_in_allowed_files_detected(tmp_path: Path):
    task_dir = tmp_path / "target_mismatch"
    task_dir.mkdir()
    data = {
        "id": "mismatch-task",
        "title": "Mismatch",
        "objective": "Objective",
        "target_file": "module.py",
        "allowed_files": ["other.py"],
        "starting_state": "State",
        "expected_behavior": "Expected",
        "test_criteria": {"c": "rule"},
        "failure_category": "CORRECTNESS_FAILURE",
        "scoring_rule": "Binary",
    }
    (task_dir / "task.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SpecificationError, match="target_file 'module.py' must be included in allowed_files"):
        load_task_spec(task_dir)


def test_missing_workspace_or_target_file_detected(tmp_path: Path):
    task_dir = tmp_path / "no_workspace_file"
    task_dir.mkdir()
    data = {
        "id": "task-test",
        "title": "Test",
        "objective": "Objective",
        "target_file": "missing.py",
        "allowed_files": ["missing.py"],
        "starting_state": "State",
        "expected_behavior": "Expected",
        "test_criteria": {"c": "rule"},
        "failure_category": "CORRECTNESS_FAILURE",
        "scoring_rule": "Binary",
    }
    (task_dir / "task.json").write_text(json.dumps(data), encoding="utf-8")
    workspace = task_dir / "workspace"
    workspace.mkdir()
    # Notice: missing.py is not created inside workspace!

    with pytest.raises(SpecificationError, match="Target file 'missing.py' not found in workspace"):
        load_task_spec(task_dir)


def test_discover_tasks_detects_malformed_spec_without_crashing(tmp_path: Path):
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()

    # Valid task
    valid_dir = tasks_root / "valid"
    valid_dir.mkdir()
    (valid_dir / "task.json").write_text(json.dumps({
        "id": "valid-01",
        "title": "Valid",
        "objective": "Obj",
        "target_file": "app.py",
        "allowed_files": ["app.py"],
        "starting_state": "S",
        "expected_behavior": "E",
        "test_criteria": {"c": "ok"},
        "failure_category": "CORRECTNESS_FAILURE",
        "scoring_rule": "Rule",
    }), encoding="utf-8")
    (valid_dir / "workspace").mkdir()
    (valid_dir / "workspace" / "app.py").write_text("# ok", encoding="utf-8")
    (valid_dir / "tests").mkdir()

    # Broken task
    broken_dir = tasks_root / "broken"
    broken_dir.mkdir()
    (broken_dir / "task.json").write_text("{}", encoding="utf-8")

    discovered = discover_tasks(tasks_root)
    assert len(discovered) == 2
    # One is valid, one has error
    specs = [s for _, s, _ in discovered if s is not None]
    errors = [e for _, _, e in discovered if e is not None]
    assert len(specs) == 1
    assert specs[0].id == "valid-01"
    assert len(errors) == 1
    assert "missing required fields" in errors[0]

