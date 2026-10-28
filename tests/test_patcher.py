"""Unit tests for the pure-Python unified diff parser and applier."""

import pytest
from safecode_eval.patcher import (
    PatchApplicationError,
    apply_hunks_to_text,
    apply_patch_to_file_content,
    parse_unified_diff_hunks,
)


def test_parse_unified_diff_hunks():
    diff = """--- a/hello.py
+++ b/hello.py
@@ -1,3 +1,3 @@
 def greeting():
-    return "hello"
+    return "hello world"
"""
    hunks = parse_unified_diff_hunks(diff)
    assert "hello.py" in hunks
    assert len(hunks["hello.py"]) == 1
    start, count, lines = hunks["hello.py"][0]
    assert start == 1
    assert count == 3
    assert len(lines) == 3


def test_apply_patch_successful():
    original = """def greeting():
    return "hello"
"""
    diff = """--- a/hello.py
+++ b/hello.py
@@ -1,2 +1,2 @@
 def greeting():
-    return "hello"
+    return "hello world"
"""
    result = apply_patch_to_file_content(original, diff, "hello.py")
    expected = """def greeting():
    return "hello world"
"""
    assert result == expected


def test_apply_patch_context_mismatch_raises_error():
    original = """def greeting():
    return "completely different line"
"""
    diff = """--- a/hello.py
+++ b/hello.py
@@ -1,2 +1,2 @@
 def greeting():
-    return "hello"
+    return "hello world"
"""
    with pytest.raises(PatchApplicationError, match="Context mismatch|Deletion mismatch"):
        apply_patch_to_file_content(original, diff, "hello.py")


def test_apply_patch_missing_target_file_in_diff():
    original = "a = 1"
    diff = """--- a/foo.py
+++ b/foo.py
@@ -1,1 +1,1 @@
-a = 1
+a = 2
"""
    with pytest.raises(PatchApplicationError, match="No hunks found in patch for target file"):
        apply_patch_to_file_content(original, diff, "bar.py")

