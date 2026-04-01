"""Render unified coverage reports as markdown for documentation.

Produces a markdown section with summary stats and per-file coverage table,
suitable for inclusion in generated docs.
"""

from __future__ import annotations

from .model import CoverageReport


def render_coverage_markdown(reports: list[CoverageReport]) -> str:
    """Render one or more coverage reports as a markdown section.

    Args:
        reports: List of CoverageReport objects to render.

    Returns:
        Markdown string with coverage summary and file tables.
        Empty string if no reports or no files.
    """
    if not reports:
        return ""

    all_files = []
    for r in reports:
        all_files.extend(r.files)

    if not all_files:
        return ""

    lines: list[str] = []
    lines.append("## Test Coverage\n")

    # Overall summary
    total_lines = sum(f.lines_total for f in all_files)
    total_covered = sum(f.lines_covered for f in all_files)
    overall_rate = (total_covered / total_lines * 100) if total_lines > 0 else 0.0

    total_branches = sum(f.branches_total for f in all_files)
    total_branches_covered = sum(f.branches_covered for f in all_files)

    total_functions = sum(f.functions_total for f in all_files)
    total_functions_covered = sum(f.functions_covered for f in all_files)

    lines.append("### Summary\n")
    lines.append("| Metric | Covered | Total | Rate |")
    lines.append("|--------|--------:|------:|-----:|")
    lines.append(f"| Lines | {total_covered} | {total_lines} | {overall_rate:.1f}% |")

    if total_branches > 0:
        branch_pct = total_branches_covered / total_branches * 100
        lines.append(f"| Branches | {total_branches_covered} | {total_branches} | {branch_pct:.1f}% |")

    if total_functions > 0:
        func_pct = total_functions_covered / total_functions * 100
        lines.append(f"| Functions | {total_functions_covered} | {total_functions} | {func_pct:.1f}% |")

    lines.append("")

    # Badge-style indicator
    badge = _coverage_badge(overall_rate)
    lines.append(f"**Overall coverage**: {badge} {overall_rate:.1f}%\n")

    # Per-file table (sorted by line rate ascending — worst first)
    sorted_files = sorted(all_files, key=lambda f: f.line_rate)

    # Cap to top 30 files to keep docs manageable
    display_files = sorted_files[:30]
    has_branches = any(f.branches_total > 0 for f in display_files)
    has_functions = any(f.functions_total > 0 for f in display_files)

    lines.append("### Per-File Coverage\n")

    # Build header
    header = "| File | Lines |"
    separator = "|------|------:|"
    if has_branches:
        header += " Branches |"
        separator += "---------:|"
    if has_functions:
        header += " Functions |"
        separator += "----------:|"

    lines.append(header)
    lines.append(separator)

    for f in display_files:
        row = f"| `{_shorten_path(f.path)}` | {f.line_rate * 100:.0f}% |"
        if has_branches:
            br = f"{f.branch_rate * 100:.0f}%" if f.branch_rate is not None else "—"
            row += f" {br} |"
        if has_functions:
            fr = f"{f.function_rate * 100:.0f}%" if f.function_rate is not None else "—"
            row += f" {fr} |"
        lines.append(row)

    if len(sorted_files) > 30:
        lines.append(f"\n*... and {len(sorted_files) - 30} more files*\n")

    # Source info
    sources = list({r.source_format for r in reports})
    lines.append(f"\n> Coverage data from: {', '.join(sources)}")

    return "\n".join(lines) + "\n"


def _coverage_badge(rate: float) -> str:
    """Return a text badge based on coverage percentage."""
    if rate >= 80:
        return "HIGH"
    elif rate >= 60:
        return "MEDIUM"
    else:
        return "LOW"


def _shorten_path(path: str, max_len: int = 60) -> str:
    """Shorten a file path for table display."""
    if len(path) <= max_len:
        return path
    parts = path.split("/")
    if len(parts) <= 2:
        return path[:max_len - 3] + "..."
    # Keep first and last parts, abbreviate middle
    return parts[0] + "/.../" + "/".join(parts[-2:])
