"""Tests for program_slicing — compute minimal line sets for understanding changes."""

import tempfile
from pathlib import Path

import pytest

from repoforge.program_slicing import (
    ProgramSlice,
    SliceLine,
    compute_slice,
    format_slice,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def python_project(tmp_path):
    """Create a temp Python project with various code patterns."""
    (tmp_path / "simple.py").write_text(
        "import os\n"
        "\n"
        "x = 10\n"
        "y = x + 5\n"
        "z = y * 2\n"
        "print(z)\n"
    )

    (tmp_path / "functions.py").write_text(
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def process(data):\n"
        "    cleaned = data.strip()\n"
        "    result = cleaned.upper()\n"
        "    return result\n"
        "\n"
        "\n"
        "def main():\n"
        "    raw = Path('input.txt').read_text()\n"
        "    output = process(raw)\n"
        "    print(output)\n"
    )

    (tmp_path / "control_flow.py").write_text(
        "def check(value):\n"
        "    if value > 0:\n"
        "        result = value * 2\n"
        "    else:\n"
        "        result = 0\n"
        "    return result\n"
    )

    (tmp_path / "class_example.py").write_text(
        "class Calculator:\n"
        "    def __init__(self, base):\n"
        "        self.base = base\n"
        "\n"
        "    def add(self, n):\n"
        "        return self.base + n\n"
        "\n"
        "    def multiply(self, n):\n"
        "        return self.base * n\n"
    )

    (tmp_path / "app.ts").write_text(
        "import { useState } from 'react';\n"
        "\n"
        "const count = 0;\n"
        "const doubled = count * 2;\n"
        "console.log(doubled);\n"
    )

    return tmp_path


# ---------------------------------------------------------------------------
# ProgramSlice data model
# ---------------------------------------------------------------------------


class TestProgramSlice:
    def test_empty_slice(self):
        ps = ProgramSlice(file="a.py", target_line=1, target_content="x = 1",
                          scope_name="<module>", total_file_lines=10)
        assert ps.reduction_ratio == 1.0  # no lines in slice
        assert ps.line_numbers == []

    def test_reduction_ratio(self):
        ps = ProgramSlice(
            file="a.py", target_line=5, target_content="z = x + y",
            scope_name="<module>", total_file_lines=10,
            lines=[
                SliceLine(3, "x = 1", "def"),
                SliceLine(4, "y = 2", "def"),
                SliceLine(5, "z = x + y", "target"),
            ],
        )
        assert ps.reduction_ratio == pytest.approx(0.7)
        assert ps.line_numbers == [3, 4, 5]

    def test_zero_total_lines(self):
        ps = ProgramSlice(file="a.py", target_line=1, target_content="",
                          scope_name="<module>", total_file_lines=0)
        assert ps.reduction_ratio == 0.0


# ---------------------------------------------------------------------------
# Python slicing
# ---------------------------------------------------------------------------


class TestPythonSlicing:
    def test_includes_target_line(self, python_project):
        result = compute_slice(str(python_project), "simple.py", 4)
        assert result.target_line == 4
        assert any(sl.line_number == 4 and sl.reason == "target" for sl in result.lines)

    def test_backward_slice_finds_definition(self, python_project):
        # Line 4: y = x + 5 — should find x = 10 on line 3
        result = compute_slice(str(python_project), "simple.py", 4)
        line_nums = result.line_numbers
        assert 3 in line_nums  # x = 10

    def test_forward_slice_finds_usage(self, python_project):
        # Line 3: x = 10 — should find y = x + 5 on line 4
        result = compute_slice(str(python_project), "simple.py", 3)
        line_nums = result.line_numbers
        assert 4 in line_nums  # y = x + 5

    def test_function_scope_detected(self, python_project):
        # Line 5: cleaned = data.strip() is inside process()
        result = compute_slice(str(python_project), "functions.py", 5)
        assert result.scope_name == "process"

    def test_includes_function_definition(self, python_project):
        result = compute_slice(str(python_project), "functions.py", 6)
        # Should include the function def line
        assert any(sl.reason == "scope" for sl in result.lines)

    def test_includes_relevant_imports(self, python_project):
        # Line 11: raw = Path('input.txt').read_text() — should include Path import
        result = compute_slice(str(python_project), "functions.py", 11)
        import_lines = [sl for sl in result.lines if sl.reason == "import"]
        assert len(import_lines) >= 1

    def test_control_flow_included(self, python_project):
        # Line 3: result = value * 2 — should include the if on line 2
        result = compute_slice(str(python_project), "control_flow.py", 3)
        line_nums = result.line_numbers
        assert 2 in line_nums  # if value > 0

    def test_class_method_scope(self, python_project):
        # Line 6: return self.base + n — inside add()
        result = compute_slice(str(python_project), "class_example.py", 6)
        assert result.scope_name == "add"

    def test_reduction_ratio_is_positive(self, python_project):
        result = compute_slice(str(python_project), "functions.py", 5)
        assert result.reduction_ratio > 0

    def test_out_of_range_line(self, python_project):
        result = compute_slice(str(python_project), "simple.py", 999)
        assert result.scope_name == "<out-of-range>"
        assert len(result.lines) == 0

    def test_nonexistent_file(self, python_project):
        result = compute_slice(str(python_project), "nonexistent.py", 1)
        assert result.scope_name == "<error>"


# ---------------------------------------------------------------------------
# Generic (non-Python) slicing
# ---------------------------------------------------------------------------


class TestGenericSlicing:
    def test_typescript_target_included(self, python_project):
        result = compute_slice(str(python_project), "app.ts", 4)
        assert result.target_line == 4
        assert any(sl.line_number == 4 for sl in result.lines)

    def test_typescript_backward_slice(self, python_project):
        # Line 4: const doubled = count * 2 — should find count on line 3
        result = compute_slice(str(python_project), "app.ts", 4)
        line_nums = result.line_numbers
        assert 3 in line_nums  # const count = 0

    def test_typescript_import_included(self, python_project):
        # Line 4 uses 'count', but the import should still be available
        result = compute_slice(str(python_project), "app.ts", 4)
        # At minimum target and its dependency are included
        assert len(result.lines) >= 2


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


class TestFormatSlice:
    def test_format_basic(self):
        ps = ProgramSlice(
            file="app.py", target_line=5, target_content="z = x + y",
            scope_name="process", total_file_lines=20,
            lines=[
                SliceLine(1, "import os", "import"),
                SliceLine(3, "x = 10", "def"),
                SliceLine(5, "z = x + y", "target"),
            ],
        )
        output = format_slice(ps)
        assert "## Program Slice" in output
        assert "app.py" in output
        assert "process" in output
        assert ">>>" in output  # target marker
        assert "[def]" in output
        assert "[import]" in output
        assert "..." in output  # gap marker between line 1 and 3

    def test_format_empty_slice(self):
        ps = ProgramSlice(
            file="a.py", target_line=1, target_content="",
            scope_name="<out-of-range>", total_file_lines=10,
        )
        output = format_slice(ps)
        assert "No slice computed" in output

    def test_format_legend(self):
        ps = ProgramSlice(
            file="a.py", target_line=1, target_content="x = 1",
            scope_name="fn", total_file_lines=1,
            lines=[SliceLine(1, "x = 1", "target")],
        )
        output = format_slice(ps)
        assert "Legend" in output
