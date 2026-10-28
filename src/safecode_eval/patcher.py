"""Pure-Python unified diff parser and applier with scope enforcement."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple


class PatchApplicationError(Exception):
    """Raised when a patch cannot be applied cleanly to the target content."""


def parse_unified_diff_hunks(diff_text: str) -> Dict[str, List[Tuple[int, int, List[str]]]]:
    """Parses a unified diff into per-file hunks.

    Returns a mapping of relative file paths to lists of hunks:
    (orig_start_line, orig_line_count, hunk_lines)
    """
    file_hunks: Dict[str, List[Tuple[int, int, List[str]]]] = {}
    lines = diff_text.splitlines(keepends=True)

    current_file: str | None = None
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # Look for target header +++ b/path/to/file or +++ path/to/file
        if line.startswith("+++ "):
            target_match = re.match(r"^\+\+\+\s+(?:[bB]/)?([^\s\t\n]+)", line)
            if target_match:
                raw_path = target_match.group(1).strip()
                if raw_path != "/dev/null":
                    current_file = raw_path.replace("\\", "/").lstrip("/")
                    if current_file not in file_hunks:
                        file_hunks[current_file] = []
            i += 1
            continue

        # Look for hunk header @@ -start,count +start,count @@
        if line.startswith("@@ ") and current_file is not None:
            hunk_match = re.match(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@", line)
            if hunk_match:
                orig_start = int(hunk_match.group(1))
                orig_count = int(hunk_match.group(2)) if hunk_match.group(2) is not None else 1
                i += 1
                hunk_lines: List[str] = []
                while i < n and not lines[i].startswith("@@ ") and not lines[i].startswith("--- "):
                    # Ignore git diff meta lines like '\ No newline at end of file'
                    if not lines[i].startswith("\\"):
                        hunk_lines.append(lines[i])
                    i += 1
                file_hunks[current_file].append((orig_start, orig_count, hunk_lines))
                continue

        i += 1

    return file_hunks


def _normalize_hunk_line(hline: str) -> Tuple[str, str]:
    """Returns (marker, content) for a hunk line."""
    if not hline:
        return (" ", "")
    marker = hline[0]
    if marker in ("+", "-"):
        return (marker, hline[1:])
    if marker == " ":
        return (" ", hline[1:])
    # Line without leading space (e.g. empty line \n in diff)
    return (" ", hline)


def find_matching_offset(orig_lines: List[str], expected: List[str], hint_idx: int) -> int:
    """Finds the line index where the hunk's expected context and removal lines match."""
    if not expected:
        return hint_idx

    num_expected = len(expected)
    num_orig = len(orig_lines)

    # 1. Check at hint_idx first
    if 0 <= hint_idx <= num_orig - num_expected:
        if all(orig_lines[hint_idx + k].rstrip("\r\n") == expected[k] for k in range(num_expected)):
            return hint_idx

    # 2. Search radiating outwards from hint_idx
    max_delta = max(hint_idx, num_orig - hint_idx)
    for delta in range(1, max_delta + 1):
        for candidate in (hint_idx - delta, hint_idx + delta):
            if 0 <= candidate <= num_orig - num_expected:
                if all(orig_lines[candidate + k].rstrip("\r\n") == expected[k] for k in range(num_expected)):
                    return candidate

    return -1


def apply_hunks_to_text(original_text: str, hunks: List[Tuple[int, int, List[str]]]) -> str:
    """Applies a list of hunks to original text content with offset resolution."""
    orig_lines = original_text.splitlines(keepends=True)
    out_lines: List[str] = []
    orig_idx = 0

    # Ensure hunks are sorted by orig_start
    sorted_hunks = sorted(hunks, key=lambda h: h[0])

    for orig_start, orig_count, hunk_lines in sorted_hunks:
        hint_idx = max(0, orig_start - 1)

        # Extract sequence of expected context and deleted lines
        expected: List[str] = []
        for hline in hunk_lines:
            marker, content = _normalize_hunk_line(hline)
            if marker in (" ", "-"):
                expected.append(content.rstrip("\r\n"))

        target_idx = find_matching_offset(orig_lines, expected, hint_idx)
        if target_idx == -1:
            target_idx = hint_idx

        # Copy unchanged lines leading up to target_idx
        while orig_idx < target_idx and orig_idx < len(orig_lines):
            out_lines.append(orig_lines[orig_idx])
            orig_idx += 1

        for hline in hunk_lines:
            marker, content = _normalize_hunk_line(hline)

            if marker == " ":
                # Context line: must match original
                if orig_idx < len(orig_lines):
                    if orig_lines[orig_idx].rstrip("\r\n") != content.rstrip("\r\n"):
                        raise PatchApplicationError(
                            f"Context mismatch at line {orig_idx + 1}:\n"
                            f"Expected: {content!r}\n"
                            f"Found:    {orig_lines[orig_idx]!r}"
                        )
                    out_lines.append(orig_lines[orig_idx])
                    orig_idx += 1
                else:
                    out_lines.append(content)
            elif marker == "-":
                # Removed line: should match original line
                if orig_idx < len(orig_lines):
                    if orig_lines[orig_idx].rstrip("\r\n") != content.rstrip("\r\n"):
                        raise PatchApplicationError(
                            f"Deletion mismatch at line {orig_idx + 1}:\n"
                            f"Expected to remove: {content!r}\n"
                            f"Found:             {orig_lines[orig_idx]!r}"
                        )
                    orig_idx += 1
                else:
                    raise PatchApplicationError(f"Unexpected end of file trying to delete: {content!r}")
            elif marker == "+":
                # Added line
                out_lines.append(content)

    # Copy any remaining lines after all hunks
    while orig_idx < len(orig_lines):
        out_lines.append(orig_lines[orig_idx])
        orig_idx += 1

    return "".join(out_lines)


def apply_patch_to_file_content(original_text: str, patch_text: str, target_file: str) -> str:
    """Applies a patch specifically to the named target file."""
    hunks_by_file = parse_unified_diff_hunks(patch_text)
    norm_target = target_file.replace("\\", "/").lstrip("/")

    if norm_target not in hunks_by_file:
        matches = [k for k in hunks_by_file if k.endswith(norm_target) or norm_target.endswith(k)]
        if matches:
            norm_target = matches[0]
        else:
            raise PatchApplicationError(f"No hunks found in patch for target file '{target_file}'")

    return apply_hunks_to_text(original_text, hunks_by_file[norm_target])
