"""Tests for Wave 15: Advanced intelligence — dead code, complexity, examples."""

import pytest

from repoforge.intelligence.ast_extractor import ASTSymbol
from repoforge.analysis import (
    detect_dead_code,
    analyze_complexity,
    extract_code_examples,
    DeadCodeReport,
    ComplexityReport,
    ModuleComplexity,
    CodeExample,
)


# ── helpers ──────────────────────────────────────────────────────────────


def _sym(name, kind="function", file="a.py", signature="", params=None,
         return_type=None, line=1):
    return ASTSymbol(
        name=name, kind=kind, signature=signature or f"def {name}()",
        file=file, line=line, params=params or [], return_type=return_type,
    )


# ── Dead code detection ──────────────────────────────────────────────────


class TestDeadCode:

    def test_returns_report(self):
        symbols = {
            "a.py": [_sym("used_fn", file="a.py"), _sym("unused_fn", file="a.py")],
            "b.py": [_sym("caller", file="b.py", signature="def caller(): used_fn()")],
        }
        report = detect_dead_code(symbols)
        assert isinstance(report, DeadCodeReport)

    def test_detects_unreferenced_functions(self):
        symbols = {
            "a.py": [_sym("public_fn", file="a.py"), _sym("orphan_fn", file="a.py")],
            "b.py": [_sym("caller", file="b.py",
                          signature="def caller(): return public_fn()")],
        }
        report = detect_dead_code(symbols)
        orphans = [s.name for s in report.unreferenced]
        # orphan_fn is never referenced by any other symbol's signature
        assert "orphan_fn" in orphans

    def test_main_and_init_excluded(self):
        symbols = {
            "main.py": [_sym("main", file="main.py")],
            "__init__.py": [_sym("setup", file="__init__.py")],
        }
        report = detect_dead_code(symbols)
        names = [s.name for s in report.unreferenced]
        assert "main" not in names
        assert "setup" not in names

    def test_empty_symbols(self):
        report = detect_dead_code({})
        assert report.unreferenced == []

    def test_classes_not_flagged_as_dead(self):
        symbols = {
            "models.py": [_sym("User", kind="class", file="models.py")],
        }
        report = detect_dead_code(symbols)
        names = [s.name for s in report.unreferenced]
        # Classes are often used externally — don't flag them
        assert "User" not in names


# ── Complexity analysis ──────────────────────────────────────────────────


class TestComplexityAnalysis:

    def _make_file(self, tmp_path, name, content):
        f = tmp_path / name
        f.write_text(content)
        return str(f)

    def test_returns_report(self, tmp_path):
        self._make_file(tmp_path, "simple.py", "def foo():\n    return 1\n")
        report = analyze_complexity({str(tmp_path / "simple.py"): "def foo():\n    return 1\n"})
        assert isinstance(report, ComplexityReport)

    def test_simple_function_low_complexity(self):
        report = analyze_complexity({"a.py": "def foo():\n    return 1\n"})
        assert len(report.modules) >= 1
        assert report.modules[0].avg_complexity <= 3

    def test_complex_function_higher_score(self):
        complex_code = """def process(x):
    if x > 0:
        if x > 10:
            if x > 100:
                return "big"
            else:
                return "medium"
        elif x > 5:
            return "small-ish"
        else:
            return "small"
    elif x == 0:
        return "zero"
    else:
        for i in range(x):
            if i % 2 == 0:
                continue
            try:
                do_something(i)
            except ValueError:
                pass
        return "negative"
"""
        report = analyze_complexity({"a.py": complex_code})
        assert report.modules[0].avg_complexity > 3

    def test_empty_files(self):
        report = analyze_complexity({})
        assert report.modules == []

    def test_module_has_file_and_functions(self):
        code = "def foo():\n    return 1\n\ndef bar():\n    if True:\n        return 2\n"
        report = analyze_complexity({"app.py": code})
        assert report.modules[0].file == "app.py"
        assert report.modules[0].function_count >= 2


# ── Code example extraction ─────────────────────────────────────────────


class TestCodeExamples:

    def test_extracts_from_test_files(self):
        test_content = {
            "tests/test_app.py": (
                "def test_create_user():\n"
                "    user = create_user('Alice')\n"
                "    assert user.name == 'Alice'\n"
            ),
        }
        examples = extract_code_examples(test_content)
        assert len(examples) >= 1
        assert isinstance(examples[0], CodeExample)

    def test_example_has_fields(self):
        test_content = {
            "tests/test_app.py": (
                "def test_hello():\n"
                "    result = greet('Bob')\n"
                "    assert result == 'Hello, Bob!'\n"
            ),
        }
        examples = extract_code_examples(test_content)
        ex = examples[0]
        assert ex.source_file == "tests/test_app.py"
        assert ex.function_name == "test_hello"
        assert "greet" in ex.code

    def test_empty_input(self):
        assert extract_code_examples({}) == []

    def test_non_test_files_skipped(self):
        content = {
            "app.py": "def main():\n    print('hello')\n",
        }
        examples = extract_code_examples(content)
        assert examples == []

    def test_strips_assert_for_usage_example(self):
        test_content = {
            "tests/test_math.py": (
                "def test_add():\n"
                "    result = add(2, 3)\n"
                "    assert result == 5\n"
            ),
        }
        examples = extract_code_examples(test_content)
        assert len(examples) >= 1
        # The code should contain the usage but not necessarily the assert
        assert "add(2, 3)" in examples[0].code
