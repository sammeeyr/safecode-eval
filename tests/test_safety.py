"""Unit tests for AST pre-execution safety guard and patch scope validation."""

import pytest
from safecode_eval.models import SafetyViolationError, ScopeViolationError
from safecode_eval.safety import validate_patch_scope, verify_code_safety


def test_scope_validation_accepts_allowed_targets():
    patch = """--- a/calculator.py
+++ b/calculator.py
@@ -1,3 +1,3 @@
-def foo(): pass
+def foo(): return 42
"""
    targets = validate_patch_scope(patch, allowed_files=["calculator.py"])
    assert targets == ["calculator.py"]


def test_scope_validation_rejects_out_of_scope_target():
    patch = """--- a/other_file.py
+++ b/other_file.py
@@ -1,2 +1,2 @@
-def bar(): pass
+def bar(): return 1
"""
    with pytest.raises(ScopeViolationError, match="outside the allowed scope"):
        validate_patch_scope(patch, allowed_files=["calculator.py"])


def test_scope_validation_rejects_directory_traversal():
    patch = """--- a/../etc/passwd
+++ b/../etc/passwd
@@ -1,2 +1,2 @@
-root
+pwned
"""
    with pytest.raises(ScopeViolationError, match="Directory traversal detected"):
        validate_patch_scope(patch, allowed_files=["calculator.py"])


def test_scope_validation_rejects_empty_patch():
    with pytest.raises(ScopeViolationError, match="does not specify any target files"):
        validate_patch_scope("Just some random text without headers", allowed_files=["calculator.py"])


def test_ast_safety_accepts_benign_code():
    benign_code = """
import math
from typing import List, Dict

def compute_average(values: List[float]) -> float:
    if not values:
        return 0.0
    return math.fsum(values) / len(values)
"""
    # Should not raise
    verify_code_safety(benign_code, filename="benign.py")


def test_ast_safety_blocks_dangerous_modules():
    dangerous_snippets = [
        "import os\nos.system('echo pwned')",
        "import subprocess\nsubprocess.run(['dir'])",
        "import socket\ns = socket.socket()",
        "import ctypes\nctypes.c_int(1)",
        "import shutil\nshutil.rmtree('.')",
        "from os import path",
        "from subprocess import Popen",
    ]
    for snippet in dangerous_snippets:
        with pytest.raises(SafetyViolationError, match="Blocked import"):
            verify_code_safety(snippet, filename="untrusted.py")


def test_ast_safety_blocks_dangerous_calls():
    dangerous_calls = [
        "eval('2 + 2')",
        "exec('a = 1')",
        "__import__('os').system('ls')",
        "compile('x = 1', '', 'exec')",
    ]
    for code in dangerous_calls:
        with pytest.raises(SafetyViolationError, match="Blocked call"):
            verify_code_safety(code, filename="untrusted.py")


def test_ast_safety_blocks_sandbox_escape_attributes():
    dangerous_attrs = [
        "cls = ().__class__.__subclasses__()",
        "fn.__globals__['os']",
        "f = func.__code__",
    ]
    for code in dangerous_attrs:
        with pytest.raises(SafetyViolationError, match="Blocked access to protected attribute"):
            verify_code_safety(code, filename="untrusted.py")


def test_ast_safety_raises_syntax_error_on_invalid_code():
    bad_syntax = "def broken_func(:\n    pass"
    with pytest.raises(SyntaxError):
        verify_code_safety(bad_syntax, filename="invalid.py")

