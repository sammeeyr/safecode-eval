"""Execution engine and sandboxed benchmark runner for SafeCode Eval."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from safecode_eval.models import (
    BenchmarkReport,
    FailureCategory,
    SafetyViolationError,
    ScopeViolationError,
    SpecificationError,
    TaskResult,
    TaskSpec,
)
from safecode_eval.patcher import PatchApplicationError, apply_patch_to_file_content
from safecode_eval.safety import validate_patch_scope, verify_code_safety
from safecode_eval.scoring import build_benchmark_report, evaluate_task_outcome


def load_task_spec(task_dir: Path) -> TaskSpec:
    """Loads and validates a task specification from a directory."""
    spec_path = task_dir / "task.json"
    if not spec_path.is_file():
        raise SpecificationError(f"Missing task.json in '{task_dir}'")
    spec = TaskSpec.from_file(spec_path)

    # Verify workspace target file exists in task definition
    workspace_dir = task_dir / "workspace"
    if not workspace_dir.is_dir():
        raise SpecificationError(f"Missing 'workspace' directory in '{task_dir}'")

    target_path = workspace_dir / spec.target_file
    if not target_path.is_file():
        raise SpecificationError(
            f"Target file '{spec.target_file}' not found in workspace '{workspace_dir}'"
        )

    # Verify tests directory exists
    tests_dir = task_dir / "tests"
    if not tests_dir.is_dir():
        raise SpecificationError(f"Missing 'tests' directory in '{task_dir}'")

    return spec


def discover_tasks(tasks_root: Path) -> List[Tuple[Path, Optional[TaskSpec], Optional[str]]]:
    """Scans a directory for tasks, detecting valid, malformed, and missing specs."""
    discovered: List[Tuple[Path, Optional[TaskSpec], Optional[str]]] = []
    if not tasks_root.is_dir():
        return discovered

    for entry in sorted(tasks_root.iterdir()):
        if entry.is_dir() and not entry.name.startswith("."):
            try:
                spec = load_task_spec(entry)
                discovered.append((entry, spec, None))
            except SpecificationError as err:
                discovered.append((entry, None, str(err)))

    return discovered


def resolve_evaluator_python() -> str:
    """Resolves the preferred Python interpreter (active venv, project .venv, or sys.executable)."""
    # 1. If currently running in a virtual environment, use sys.executable
    if sys.prefix != sys.base_prefix:
        return sys.executable

    # 2. If a local .venv exists in current workspace, prefer its interpreter
    venv_py_win = Path(".venv/Scripts/python.exe")
    if venv_py_win.is_file():
        return str(venv_py_win.resolve())
    venv_py_unix = Path(".venv/bin/python")
    if venv_py_unix.is_file():
        return str(venv_py_unix.resolve())

    return sys.executable


def run_sandboxed_test_suite(
    sandbox_dir: Path,
    timeout_seconds: float = 12.0,
) -> Tuple[bool, bool, bool, Dict[str, Any], float, Optional[str]]:
    """Runs all deterministic test suites for a task in an isolated subprocess.

    Returns:
    (regression_passed, correctness_passed, security_passed, test_details, elapsed_seconds, timeout_msg)
    """
    clean_env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
        "SYSTEMDRIVE": os.environ.get("SYSTEMDRIVE", "C:"),
        "WINDIR": os.environ.get("WINDIR", "C:\\Windows"),
        "TEMP": os.environ.get("TEMP", tempfile.gettempdir()),
        "TMP": os.environ.get("TMP", tempfile.gettempdir()),
        "APPDATA": os.environ.get("APPDATA", ""),
        "LOCALAPPDATA": os.environ.get("LOCALAPPDATA", ""),
        "USERPROFILE": os.environ.get("USERPROFILE", ""),
        "PATHEXT": os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD"),
        "PYTHONSAFEPATH": "1",
        "PYTHONPATH": str(sandbox_dir),
    }

    python_exe = resolve_evaluator_python()
    cmd = [
        python_exe,
        "-m",
        "pytest",
        "tests",
        "-v",
        "--tb=short",
        "--no-header",
        "--disable-warnings",
    ]

    start_time = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(sandbox_dir),
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        elapsed = time.perf_counter() - start_time
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        full_output = stdout + ("\nSTDERR:\n" + stderr if stderr else "")

        # Parse test outcomes by file
        reg_passed = True
        corr_passed = True
        sec_passed = True
        skipped_detected = False

        # Check for FAILED / ERROR / SKIPPED entries in pytest verbose output
        for line in full_output.splitlines():
            line_str = line.strip()
            # Test failures or runtime errors
            if "test_regression.py" in line_str and ("FAILED" in line_str or "ERROR" in line_str):
                reg_passed = False
            if "test_functional.py" in line_str and ("FAILED" in line_str or "ERROR" in line_str):
                corr_passed = False
            if "test_security.py" in line_str and ("FAILED" in line_str or "ERROR" in line_str):
                sec_passed = False

            # Bypassed / skipped tests per file
            if "test_regression.py" in line_str and "SKIPPED" in line_str:
                reg_passed = False
                skipped_detected = True
            if "test_functional.py" in line_str and "SKIPPED" in line_str:
                corr_passed = False
                skipped_detected = True
            if "test_security.py" in line_str and "SKIPPED" in line_str:
                sec_passed = False
                skipped_detected = True

        # Check summary line for any skipped tests (e.g. "7 passed, 4 skipped in 0.25s")
        if re.search(r"\b(\d+)\s+skipped\b", full_output):
            skipped_detected = True
            corr_passed = False

        # Verify that tests actually executed and passed (must have at least one passed and no zero-run)
        passed_match = re.search(r"\b(\d+)\s+passed\b", full_output)
        if not passed_match or int(passed_match.group(1)) == 0:
            corr_passed = False

        # If pytest exit code is non-zero but no specific failure line was matched (e.g. collection error)
        if proc.returncode != 0 and reg_passed and corr_passed and sec_passed:
            corr_passed = False

        test_details = {
            "exit_code": proc.returncode,
            "regression_passed": reg_passed,
            "correctness_passed": corr_passed,
            "security_passed": sec_passed,
            "skipped_detected": skipped_detected,
            "output_excerpt": full_output[:1200] if full_output else "",
        }

        return reg_passed, corr_passed, sec_passed, test_details, elapsed, None

    except subprocess.TimeoutExpired as err:
        elapsed = time.perf_counter() - start_time
        timeout_msg = f"Execution timed out after {timeout_seconds}s: {err}"
        test_details = {"error": timeout_msg}
        return False, False, False, test_details, elapsed, timeout_msg

    except Exception as err:
        elapsed = time.perf_counter() - start_time
        err_msg = f"Unexpected execution error: {err}"
        test_details = {"error": err_msg}
        return False, False, False, test_details, elapsed, err_msg


def evaluate_task_patch(
    task_dir: Path,
    patch_text: str,
    spec: Optional[TaskSpec] = None,
    timeout_seconds: float = 12.0,
) -> TaskResult:
    """Evaluates a patch against a single task specification inside an isolated temporary directory."""
    start_total = time.perf_counter()

    # Step 1: Validate task specification
    if spec is None:
        try:
            spec = load_task_spec(task_dir)
        except SpecificationError as err:
            return TaskResult(
                task_id=task_dir.name,
                passed=False,
                score=0.0,
                failure_category=FailureCategory.SPECIFICATION_ERROR,
                scope_preserved=False,
                security_preserved=False,
                regression_free=False,
                correctness_passed=False,
                execution_time_seconds=round(time.perf_counter() - start_total, 4),
                test_details={"error": str(err)},
                limitations=[],
                error_message=f"Specification error: {err}",
            )

    # Step 2: Validate patch scope
    scope_preserved = True
    try:
        validate_patch_scope(patch_text, spec.allowed_files)
    except ScopeViolationError as err:
        scope_preserved = False
        return evaluate_task_outcome(
            task_spec=spec,
            scope_preserved=False,
            security_preserved=True,
            regression_free=False,
            correctness_passed=False,
            execution_time_seconds=time.perf_counter() - start_total,
            test_details={"scope_check": "FAILED", "reason": str(err)},
            error_message=str(err),
            failure_category_override=FailureCategory.SCOPE_VIOLATION,
        )

    # Step 3: Create isolated sandbox workspace
    with tempfile.TemporaryDirectory(prefix=f"safecode_{spec.id}_") as temp_dir_str:
        sandbox_path = Path(temp_dir_str)

        # Copy workspace files
        workspace_src = task_dir / "workspace"
        for item in workspace_src.iterdir():
            dest = sandbox_path / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        # Copy test suite
        tests_src = task_dir / "tests"
        sandbox_tests = sandbox_path / "tests"
        shutil.copytree(tests_src, sandbox_tests)

        # Step 4: Apply patch inside sandbox
        target_path = sandbox_path / spec.target_file
        if not target_path.is_file():
            return evaluate_task_outcome(
                task_spec=spec,
                scope_preserved=True,
                security_preserved=False,
                regression_free=False,
                correctness_passed=False,
                execution_time_seconds=time.perf_counter() - start_total,
                test_details={"error": f"Target file '{spec.target_file}' missing from workspace."},
                error_message=f"Target file '{spec.target_file}' missing.",
                failure_category_override=FailureCategory.SPECIFICATION_ERROR,
            )

        original_code = target_path.read_text(encoding="utf-8")
        try:
            patched_code = apply_patch_to_file_content(original_code, patch_text, spec.target_file)
        except PatchApplicationError as err:
            return evaluate_task_outcome(
                task_spec=spec,
                scope_preserved=True,
                security_preserved=False,
                regression_free=False,
                correctness_passed=False,
                execution_time_seconds=time.perf_counter() - start_total,
                test_details={"patch_error": str(err)},
                error_message=f"Patch application failed: {err}",
                failure_category_override=FailureCategory.PARSE_OR_SYNTAX_ERROR,
            )

        # Step 5: AST Pre-execution Safety Guard
        try:
            verify_code_safety(patched_code, filename=spec.target_file)
        except SafetyViolationError as err:
            # Dangerous constructs detected: Never execute untrusted code on host!
            return evaluate_task_outcome(
                task_spec=spec,
                scope_preserved=True,
                security_preserved=False,
                regression_free=False,
                correctness_passed=False,
                execution_time_seconds=time.perf_counter() - start_total,
                test_details={"safety_violation": str(err)},
                error_message=f"AST Safety violation detected: {err}",
                failure_category_override=FailureCategory.SECURITY_VIOLATION,
            )
        except SyntaxError as err:
            return evaluate_task_outcome(
                task_spec=spec,
                scope_preserved=True,
                security_preserved=False,
                regression_free=False,
                correctness_passed=False,
                execution_time_seconds=time.perf_counter() - start_total,
                test_details={"syntax_error": str(err)},
                error_message=f"Syntax error in patched code: {err}",
                failure_category_override=FailureCategory.PARSE_OR_SYNTAX_ERROR,
            )

        # Write patched code safely inside sandbox
        target_path.write_text(patched_code, encoding="utf-8")

        # Step 6: Execute deterministic test suites in subprocess
        reg_passed, corr_passed, sec_passed, test_details, proc_time, timeout_msg = run_sandboxed_test_suite(
            sandbox_path, timeout_seconds=timeout_seconds
        )

        failure_override = FailureCategory.TIMEOUT_ERROR if timeout_msg else None
        total_elapsed = time.perf_counter() - start_total

        all_ok = reg_passed and corr_passed and sec_passed and not timeout_msg
        if not all_ok:
            if timeout_msg:
                err_msg = timeout_msg
            elif test_details.get("skipped_detected"):
                err_msg = "Test suite bypass detected: one or more tests were skipped."
            else:
                err_msg = "One or more test suites failed."
        else:
            err_msg = None

        return evaluate_task_outcome(
            task_spec=spec,
            scope_preserved=True,
            security_preserved=sec_passed,
            regression_free=reg_passed,
            correctness_passed=corr_passed,
            execution_time_seconds=total_elapsed,
            test_details=test_details,
            error_message=err_msg,
            failure_category_override=failure_override,
        )


def run_benchmark(
    tasks_dir: Path,
    patch_type: str = "good",
    custom_patches_dir: Optional[Path] = None,
    output_report_path: Optional[Path] = None,
) -> BenchmarkReport:
    """Runs SafeCode Eval benchmark across all discovered tasks."""
    discovered = discover_tasks(tasks_dir)
    results: List[TaskResult] = []

    for task_dir, spec, err in discovered:
        if spec is None:
            # Specification error
            res = TaskResult(
                task_id=task_dir.name,
                passed=False,
                score=0.0,
                failure_category=FailureCategory.SPECIFICATION_ERROR,
                scope_preserved=False,
                security_preserved=False,
                regression_free=False,
                correctness_passed=False,
                execution_time_seconds=0.0,
                test_details={"specification_error": err},
                limitations=[],
                error_message=f"Specification error: {err}",
            )
            results.append(res)
            continue

        # Determine patch path
        if custom_patches_dir:
            patch_file = custom_patches_dir / f"{spec.id}.patch"
        else:
            patch_file = task_dir / "patches" / f"{patch_type}.patch"

        if not patch_file.is_file():
            res = TaskResult(
                task_id=spec.id,
                passed=False,
                score=0.0,
                failure_category=FailureCategory.SPECIFICATION_ERROR,
                scope_preserved=False,
                security_preserved=False,
                regression_free=False,
                correctness_passed=False,
                execution_time_seconds=0.0,
                test_details={"error": f"Patch file not found: {patch_file}"},
                limitations=spec.limitations,
                error_message=f"Patch file not found: {patch_file}",
            )
            results.append(res)
            continue

        patch_text = patch_file.read_text(encoding="utf-8")
        task_res = evaluate_task_patch(task_dir, patch_text, spec=spec)
        results.append(task_res)

    report = build_benchmark_report(
        results=results,
        benchmark_version="0.1.0",
        extra_notes=[f"Evaluation mode: patch_type='{patch_type}'"],
    )

    if output_report_path:
        output_report_path.parent.mkdir(parents=True, exist_ok=True)
        output_report_path.write_text(report.to_json(), encoding="utf-8")

    return report


def main() -> None:
    """Command-line interface for SafeCode Eval."""
    parser = argparse.ArgumentParser(description="SafeCode Eval - Software Patch Benchmark Runner")
    parser.add_argument("--tasks-dir", type=Path, default=Path("tasks"), help="Path to tasks directory")
    parser.add_argument("--patch-type", type=str, default="good", help="Type of patch to evaluate (e.g. good, bad_regression, bad_incorrect, bad_security, bad_scope)")
    parser.add_argument("--report", type=Path, default=None, help="Output path for JSON report")
    args = parser.parse_args()

    print(f"=== SafeCode Eval MVP 0.1 ===")
    print(f"Scanning tasks in: {args.tasks_dir}")
    print(f"Evaluating patch type: {args.patch_type}")

    report = run_benchmark(
        tasks_dir=args.tasks_dir,
        patch_type=args.patch_type,
        output_report_path=args.report,
    )

    summary = report.summary
    print("\n--- Summary ---")
    print(f"Total tasks:       {summary['total_tasks']}")
    print(f"Passed tasks:      {summary['passed_tasks']}")
    print(f"Failed tasks:      {summary['failed_tasks']}")
    print(f"Pass rate:         {summary['pass_rate'] * 100:.1f}%")
    print(f"Mean score:        {summary['mean_score']:.2f}")
    print(f"Security status:   {summary.get('security_status', 'UNKNOWN')}")
    print(f"Verified safe:     {summary.get('verified_safe_pass_rate', 0.0) * 100:.1f}%")
    print(f"Security breaks:   {summary['security_violations']}")
    print(f"Regressions:       {summary['regression_failures']}")
    print(f"Correctness fails: {summary['correctness_failures']}")
    print(f"Scope violations:  {summary['scope_violations']}")

    print("\n--- Task Details ---")
    for tr in report.task_results:
        status = "PASS" if tr["passed"] else "FAIL"
        print(
            f"[{status}] {tr['task_id']} | Category: {tr['failure_category']} | "
            f"Score: {tr['score']} | Time: {tr['execution_time_seconds']}s"
        )
        if tr["error_message"]:
            print(f"       Reason: {tr['error_message']}")

    if args.report:
        print(f"\nReport saved to: {args.report}")


if __name__ == "__main__":
    main()
