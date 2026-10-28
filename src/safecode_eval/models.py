"""Data models and specification schemas for SafeCode Eval."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class FailureCategory(str, Enum):
    """Categorization of patch evaluation outcomes."""

    NONE = "NONE"
    CORRECTNESS_FAILURE = "CORRECTNESS_FAILURE"
    REGRESSION_FAILURE = "REGRESSION_FAILURE"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    SCOPE_VIOLATION = "SCOPE_VIOLATION"
    PARSE_OR_SYNTAX_ERROR = "PARSE_OR_SYNTAX_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    SPECIFICATION_ERROR = "SPECIFICATION_ERROR"


class SpecificationError(Exception):
    """Raised when a task specification is missing or malformed."""


class SafetyViolationError(Exception):
    """Raised when untrusted code attempts dangerous operations."""


class ScopeViolationError(Exception):
    """Raised when a patch attempts to modify files outside permitted scope."""


@dataclass(frozen=True)
class TaskSpec:
    """Specification schema for a benchmark evaluation task."""

    id: str
    title: str
    objective: str
    target_file: str
    allowed_files: List[str]
    starting_state: str
    expected_behavior: str
    test_criteria: Dict[str, str]
    failure_category: str
    scoring_rule: str
    limitations: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskSpec:
        required_fields = [
            "id",
            "title",
            "objective",
            "target_file",
            "allowed_files",
            "starting_state",
            "expected_behavior",
            "test_criteria",
            "failure_category",
            "scoring_rule",
        ]
        missing = [f for f in required_fields if f not in data or data[f] is None]
        if missing:
            raise SpecificationError(f"Task specification missing required fields: {', '.join(missing)}")

        if not isinstance(data["allowed_files"], list) or not data["allowed_files"]:
            raise SpecificationError("'allowed_files' must be a non-empty list of relative file paths.")

        if data["target_file"] not in data["allowed_files"]:
            raise SpecificationError(
                f"target_file '{data['target_file']}' must be included in allowed_files: {data['allowed_files']}"
            )

        if not isinstance(data["test_criteria"], dict) or not data["test_criteria"]:
            raise SpecificationError("'test_criteria' must be a non-empty dictionary of criteria descriptions.")

        limitations = data.get("limitations", [])
        if not isinstance(limitations, list):
            raise SpecificationError("'limitations' must be a list of limitation statements.")

        return cls(
            id=str(data["id"]).strip(),
            title=str(data["title"]).strip(),
            objective=str(data["objective"]).strip(),
            target_file=str(data["target_file"]).strip(),
            allowed_files=[str(f).strip() for f in data["allowed_files"]],
            starting_state=str(data["starting_state"]).strip(),
            expected_behavior=str(data["expected_behavior"]).strip(),
            test_criteria={str(k): str(v) for k, v in data["test_criteria"].items()},
            failure_category=str(data["failure_category"]).strip(),
            scoring_rule=str(data["scoring_rule"]).strip(),
            limitations=[str(item).strip() for item in limitations],
        )

    @classmethod
    def from_file(cls, path: Path) -> TaskSpec:
        if not path.is_file():
            raise SpecificationError(f"Task specification file not found: {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = json.load(f)
        except json.JSONDecodeError as err:
            raise SpecificationError(f"Malformed JSON in task specification '{path}': {err}") from err
        except Exception as err:
            raise SpecificationError(f"Failed to read task specification '{path}': {err}") from err
        return cls.from_dict(content)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskResult:
    """Evaluation result for a single task."""

    task_id: str
    passed: bool
    score: float
    failure_category: FailureCategory
    scope_preserved: bool
    security_preserved: bool
    regression_free: bool
    correctness_passed: bool
    execution_time_seconds: float
    test_details: Dict[str, Any]
    limitations: List[str]
    error_message: Optional[str] = None

    def __post_init__(self) -> None:
        if not (0.0 <= self.score <= 1.0):
            raise ValueError(f"Invalid TaskResult for '{self.task_id}': score must be between 0.0 and 1.0, got {self.score}")
        if self.passed and not self.security_preserved:
            raise ValueError(f"Invalid TaskResult for '{self.task_id}': cannot be passed when security_preserved=False.")
        if self.passed and self.score != 1.0:
            raise ValueError(f"Invalid TaskResult for '{self.task_id}': passed=True must have score=1.0, got {self.score}")
        if not self.passed and self.score != 0.0:
            raise ValueError(f"Invalid TaskResult for '{self.task_id}': passed=False must have score=0.0, got {self.score}")
        if self.passed and self.failure_category != FailureCategory.NONE:
            raise ValueError(f"Invalid TaskResult for '{self.task_id}': passed=True must have failure_category=NONE, got {self.failure_category}")

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["failure_category"] = self.failure_category.value
        return data


@dataclass
class BenchmarkReport:
    """Consolidated benchmark evaluation report."""

    benchmark_version: str
    timestamp: str
    platform: str
    python_version: str
    summary: Dict[str, Any]
    task_results: List[Dict[str, Any]]
    notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

