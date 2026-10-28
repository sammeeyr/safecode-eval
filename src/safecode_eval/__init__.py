"""SafeCode Eval: Reproducible, offline evaluation benchmark for software patches."""

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
from safecode_eval.runner import (
    discover_tasks,
    evaluate_task_patch,
    load_task_spec,
    run_benchmark,
)
from safecode_eval.safety import validate_patch_scope, verify_code_safety
from safecode_eval.scoring import build_benchmark_report, evaluate_task_outcome

__version__ = "0.1.0"

__all__ = [
    "BenchmarkReport",
    "FailureCategory",
    "PatchApplicationError",
    "SafetyViolationError",
    "ScopeViolationError",
    "SpecificationError",
    "TaskResult",
    "TaskSpec",
    "apply_patch_to_file_content",
    "build_benchmark_report",
    "discover_tasks",
    "evaluate_task_outcome",
    "evaluate_task_patch",
    "load_task_spec",
    "run_benchmark",
    "validate_patch_scope",
    "verify_code_safety",
]

