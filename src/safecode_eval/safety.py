"""Safety controls, AST pre-execution guards, and scope validation."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import List, Set

from safecode_eval.models import SafetyViolationError, ScopeViolationError

# Dangerous standard library and third-party modules that untrusted patches must never import
BLOCKED_MODULES: Set[str] = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "ctypes",
    "shutil",
    "urllib",
    "requests",
    "http",
    "winreg",
    "pty",
    "pickle",
    "shelve",
    "importlib",
    "builtins",
    "posix",
    "nt",
    "pathlib",  # Prevent arbitrary host filesystem operations by patch code
    "pytest",   # Prevent patches from manipulating evaluation test runner
}

# Functions and built-in calls that allow arbitrary code execution or introspection bypass
BLOCKED_CALLS: Set[str] = {
    "eval",
    "exec",
    "__import__",
    "compile",
    "breakpoint",
    "globals",
    "locals",
    "open",
    "getattr",
    "setattr",
    "delattr",
}

# Attributes used in standard Python sandbox escape exploits
BLOCKED_ATTRS: Set[str] = {
    "__subclasses__",
    "__globals__",
    "__code__",
    "__builtins__",
    "__dict__",
    "__class__",
}


class ASTSafetyInspector(ast.NodeVisitor):
    """AST visitor that checks for dangerous code patterns prior to execution."""

    def __init__(self, filename: str = "<source>"):
        self.filename = filename
        self.violations: List[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root_module = alias.name.split(".")[0]
            if root_module in BLOCKED_MODULES:
                self.violations.append(
                    f"Blocked import of module '{root_module}' at {self.filename}:{node.lineno}"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            root_module = node.module.split(".")[0]
            if root_module in BLOCKED_MODULES:
                self.violations.append(
                    f"Blocked import from module '{root_module}' at {self.filename}:{node.lineno}"
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name and func_name in BLOCKED_CALLS:
            self.violations.append(
                f"Blocked call to '{func_name}()' at {self.filename}:{node.lineno}"
            )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in BLOCKED_ATTRS:
            self.violations.append(
                f"Blocked access to protected attribute '{node.attr}' at {self.filename}:{node.lineno}"
            )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in ("__builtins__", "breakpoint"):
            self.violations.append(
                f"Blocked reference to '{node.id}' at {self.filename}:{node.lineno}"
            )
        self.generic_visit(node)


def verify_code_safety(code: str, filename: str = "<patch>") -> None:
    """Verifies that the provided Python code does not contain unsafe constructs."""
    try:
        tree = ast.parse(code, filename=filename)
    except SyntaxError as err:
        raise SyntaxError(f"Syntax error in code '{filename}': {err}") from err

    inspector = ASTSafetyInspector(filename=filename)
    inspector.visit(tree)

    if inspector.violations:
        raise SafetyViolationError(
            f"Safety check rejected untrusted code in {filename}: " + "; ".join(inspector.violations)
        )


def extract_diff_targets(patch_text: str) -> List[str]:
    """Extracts target file paths from a unified diff patch."""
    targets: List[str] = []
    # Match headers like '+++ b/path/to/file.py' or '+++ path/to/file.py'
    pattern = re.compile(r"^\+\+\+\s+(?:[bB]/)?([^\s\t\n]+)", re.MULTILINE)
    for match in pattern.finditer(patch_text):
        path_str = match.group(1).strip()
        if path_str and path_str != "/dev/null":
            # Normalize path separators
            norm_path = path_str.replace("\\", "/").lstrip("/")
            if norm_path not in targets:
                targets.append(norm_path)
    return targets


def validate_patch_scope(patch_text: str, allowed_files: List[str]) -> List[str]:
    """Validates that a patch only targets files within the allowed scope.

    Raises ScopeViolationError if the patch targets files outside allowed_files
    or attempts directory traversal.
    """
    targets = extract_diff_targets(patch_text)
    if not targets:
        raise ScopeViolationError("Patch does not specify any target files or is not a valid diff.")

    normalized_allowed = {f.replace("\\", "/").lstrip("/") for f in allowed_files}

    for target in targets:
        # Check for path traversal attempts
        parts = target.split("/")
        if ".." in parts or ":" in target or target.startswith("/"):
            raise ScopeViolationError(f"Directory traversal detected in target path: '{target}'")

        if target not in normalized_allowed:
            raise ScopeViolationError(
                f"Patch targets file '{target}', which is outside the allowed scope: {sorted(normalized_allowed)}"
            )

    return targets

