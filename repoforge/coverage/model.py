"""Unified coverage data model.

All parsers convert their format-specific data into these dataclasses,
providing a single internal representation for rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CoverageFile:
    """Coverage data for a single source file."""

    path: str
    line_rate: float  # 0.0 – 1.0
    branch_rate: float | None = None  # 0.0 – 1.0, None if not available
    function_rate: float | None = None  # 0.0 – 1.0, None if not available
    lines_covered: int = 0
    lines_total: int = 0
    branches_covered: int = 0
    branches_total: int = 0
    functions_covered: int = 0
    functions_total: int = 0


@dataclass
class CoverageReport:
    """Unified coverage report aggregating multiple files.

    Each parser produces one CoverageReport per coverage file parsed.
    """

    source_format: str  # "cobertura" | "lcov" | "coverage_py" | "jacoco"
    source_file: str  # path to the original coverage file
    files: list[CoverageFile] = field(default_factory=list)

    @property
    def total_lines_covered(self) -> int:
        return sum(f.lines_covered for f in self.files)

    @property
    def total_lines(self) -> int:
        return sum(f.lines_total for f in self.files)

    @property
    def overall_line_rate(self) -> float:
        total = self.total_lines
        if total == 0:
            return 0.0
        return self.total_lines_covered / total

    @property
    def total_branches_covered(self) -> int:
        return sum(f.branches_covered for f in self.files)

    @property
    def total_branches(self) -> int:
        return sum(f.branches_total for f in self.files)

    @property
    def overall_branch_rate(self) -> float | None:
        total = self.total_branches
        if total == 0:
            return None
        return self.total_branches_covered / total

    @property
    def total_functions_covered(self) -> int:
        return sum(f.functions_covered for f in self.files)

    @property
    def total_functions(self) -> int:
        return sum(f.functions_total for f in self.files)

    @property
    def overall_function_rate(self) -> float | None:
        total = self.total_functions
        if total == 0:
            return None
        return self.total_functions_covered / total
