"""
prompts_cmd.py - Generate reusable analysis prompts from codebase scanning.

Produces structured prompts that users can paste into their own LLM for
targeted code analysis.  No LLM calls needed — purely deterministic,
built from data already produced by the scanner + graph + analysis modules.

Prompt types:
  - solid        SOLID violations
  - dead-code    Dead code paths
  - security     Security review
  - architecture Architecture review
  - test-gaps    Test coverage gaps
  - performance  Performance bottlenecks
  - deps         Dependency risks
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

PROMPT_TYPES = (
    "solid",
    "dead-code",
    "security",
    "architecture",
    "test-gaps",
    "performance",
    "deps",
)


@dataclass
class AnalysisPrompt:
    """A single analysis prompt with context."""

    prompt_type: str
    title: str
    body: str
    files: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Context gathering (reuses existing scanner data)
# ---------------------------------------------------------------------------


def _gather_context(workspace: str) -> dict:
    """Scan workspace and return context dict used by prompt builders."""
    from .scanner import scan_repo

    repo_map = scan_repo(workspace)

    # Collect flat file list + file->module mapping
    files: list[str] = []
    modules: list[dict] = []
    for layer_name, layer_data in repo_map.get("layers", {}).items():
        for mod in layer_data.get("modules", []):
            files.append(mod["path"])
            modules.append({**mod, "layer": layer_name})

    # Try to get AST symbols for dead-code / complexity analysis
    ast_symbols: dict = {}
    try:
        from .intelligence.ast_extractor import extract_all_symbols

        ast_symbols = extract_all_symbols(workspace)
    except (ImportError, OSError, RuntimeError):
        # ImportError: intelligence extras not installed; others: extraction failures
        logger.debug("AST extraction unavailable, skipping enriched prompts")

    # Try to get dep health
    dep_health = None
    try:
        from .dep_health import analyze_dependency_health

        dep_health = analyze_dependency_health(workspace)
    except (ImportError, OSError, ValueError):
        # ImportError: dep_health module; OSError: manifest read; ValueError: parse errors
        logger.debug("Dependency health analysis unavailable")

    return {
        "repo_map": repo_map,
        "files": files,
        "modules": modules,
        "ast_symbols": ast_symbols,
        "dep_health": dep_health,
        "tech_stack": repo_map.get("tech_stack", []),
        "entry_points": repo_map.get("entry_points", []),
    }


# ---------------------------------------------------------------------------
# Individual prompt builders
# ---------------------------------------------------------------------------


def _build_solid_prompt(ctx: dict) -> AnalysisPrompt:
    """SOLID violations analysis prompt."""
    modules = ctx["modules"]
    # Pick top modules with most exports (likely the "god classes")
    heavy = sorted(modules, key=lambda m: len(m.get("exports", [])), reverse=True)[:15]

    file_list = "\n".join(f"- `{m['path']}` ({len(m.get('exports', []))} exports)" for m in heavy)

    body = f"""\
Analyze the following codebase for SOLID principle violations.

## Tech Stack
{', '.join(ctx['tech_stack']) or 'Not detected'}

## Files to Focus On (highest export count — potential SRP violations)
{file_list}

## What to Check
1. **Single Responsibility**: Files with many exports may have multiple responsibilities.
2. **Open/Closed**: Look for switch/if-else chains that should use polymorphism.
3. **Liskov Substitution**: Check class hierarchies for contracts that subclasses break.
4. **Interface Segregation**: Large interfaces that force implementors to stub unused methods.
5. **Dependency Inversion**: High-level modules importing concrete low-level implementations.

For each violation found, provide:
- File and approximate line
- Which SOLID principle is violated
- Concrete refactoring suggestion
"""
    return AnalysisPrompt(
        prompt_type="solid",
        title="SOLID Principle Violations",
        body=body,
        files=[m["path"] for m in heavy],
    )


def _build_dead_code_prompt(ctx: dict) -> AnalysisPrompt:
    """Dead code paths analysis prompt."""
    ast_symbols = ctx["ast_symbols"]
    modules = ctx["modules"]

    context_lines: list[str] = []

    if ast_symbols:
        from .analysis import detect_dead_code

        report = detect_dead_code(ast_symbols)
        if report.unreferenced:
            context_lines.append("## Potentially Unreferenced Functions (automated pre-scan)")
            for sym in report.unreferenced[:20]:
                context_lines.append(
                    f"- `{sym.name}` in `{sym.file}` (line {sym.line}) — {sym.signature[:80]}"
                )
            context_lines.append("")

    # List files with no imports from other modules (potential islands)
    imported_names: set[str] = set()
    for m in modules:
        imported_names.update(m.get("imports", []))

    islands = [
        m for m in modules
        if not any(exp in imported_names for exp in m.get("exports", []))
        and m.get("exports")
    ]
    if islands:
        context_lines.append("## Potentially Isolated Modules (no other module imports their exports)")
        for m in islands[:15]:
            context_lines.append(f"- `{m['path']}` exports: {', '.join(m['exports'][:5])}")

    body = f"""\
Analyze this codebase for dead code — functions, classes, and modules that are
never used or reachable from entry points.

## Entry Points
{chr(10).join(f'- `{ep}`' for ep in ctx['entry_points']) or '- Not detected'}

{chr(10).join(context_lines)}

## What to Check
1. Functions/methods never called from any execution path
2. Modules imported but whose exports are unused
3. Feature flags or config branches that can never activate
4. Deprecated code kept "just in case"
5. Test utilities that test nothing

For each dead code path, provide:
- File and function/class name
- Evidence it is unreachable
- Safe removal recommendation (or reason to keep)
"""
    return AnalysisPrompt(
        prompt_type="dead-code",
        title="Dead Code Paths",
        body=body,
        files=[m["path"] for m in islands[:15]],
    )


def _build_security_prompt(ctx: dict) -> AnalysisPrompt:
    """Security review prompt."""
    modules = ctx["modules"]
    tech_stack = ctx["tech_stack"]

    # Identify security-sensitive modules by name patterns
    sensitive_patterns = (
        "auth", "login", "token", "secret", "crypt", "password",
        "session", "permission", "middleware", "security", "api",
    )
    sensitive = [
        m for m in modules
        if any(p in m["path"].lower() for p in sensitive_patterns)
    ]

    file_list = "\n".join(f"- `{m['path']}`" for m in sensitive[:15]) if sensitive else "- No obviously sensitive modules detected — review all API/auth boundaries"

    body = f"""\
Perform a security review of this codebase.

## Tech Stack
{', '.join(tech_stack) or 'Not detected'}

## Security-Sensitive Files
{file_list}

## What to Check
1. **Authentication**: Token validation, session management, password hashing
2. **Authorization**: Missing access checks, privilege escalation paths
3. **Input Validation**: SQL injection, XSS, command injection, path traversal
4. **Secrets Management**: Hardcoded secrets, env var exposure, config leaks
5. **Dependencies**: Known CVEs in dependencies, supply chain risks
6. **Data Exposure**: PII in logs, error messages leaking internals
7. **CSRF/CORS**: Cross-origin policies, CSRF token handling

For each finding:
- Severity (Critical/High/Medium/Low)
- File and line
- Attack vector description
- Remediation with code example
"""
    return AnalysisPrompt(
        prompt_type="security",
        title="Security Review",
        body=body,
        files=[m["path"] for m in sensitive[:15]],
    )


def _build_architecture_prompt(ctx: dict) -> AnalysisPrompt:
    """Architecture review prompt."""
    repo_map = ctx["repo_map"]
    layers = repo_map.get("layers", {})
    modules = ctx["modules"]

    layer_summary = "\n".join(
        f"- **{name}** (`{data.get('path', '')}`) — {len(data.get('modules', []))} modules"
        for name, data in layers.items()
    )

    # Find cross-layer imports (potential coupling issues)
    cross_layer: list[str] = []
    exports_by_layer: dict[str, set[str]] = {}
    for m in modules:
        exports_by_layer.setdefault(m["layer"], set()).update(m.get("exports", []))

    for m in modules:
        for imp in m.get("imports", []):
            for other_layer, other_exports in exports_by_layer.items():
                if other_layer != m["layer"] and imp in other_exports:
                    cross_layer.append(f"  `{m['path']}` ({m['layer']}) imports `{imp}` from {other_layer}")
                    break
        if len(cross_layer) >= 15:
            break

    cross_layer_text = "\n".join(cross_layer) if cross_layer else "  None detected from scanner data"

    body = f"""\
Review the architecture of this codebase for design issues.

## Layer Structure
{layer_summary or 'Single-layer project'}

## Cross-Layer Dependencies
{cross_layer_text}

## What to Check
1. **Layer violations**: Are boundaries respected? Any circular dependencies?
2. **Coupling**: Which modules are tightly coupled? Can they be decoupled?
3. **Cohesion**: Are modules focused on a single domain concept?
4. **Abstractions**: Missing interfaces/protocols at layer boundaries?
5. **Scalability**: Bottleneck patterns (single DB connection, synchronous chains)?
6. **Consistency**: Are similar problems solved the same way across the codebase?

For each issue:
- Affected module(s) with file paths
- What the architectural smell is
- Refactoring approach with estimated effort (S/M/L)
"""
    return AnalysisPrompt(
        prompt_type="architecture",
        title="Architecture Review",
        body=body,
        files=[m["path"] for m in modules[:10]],
    )


def _build_test_gaps_prompt(ctx: dict) -> AnalysisPrompt:
    """Test coverage gaps prompt."""
    modules = ctx["modules"]

    # Separate test files from source files
    test_files = [m for m in modules if _is_test_module(m["path"])]
    source_files = [m for m in modules if not _is_test_module(m["path"])]

    # Find source files with no corresponding test
    tested_names = {_test_target_name(m["path"]) for m in test_files}
    untested = [
        m for m in source_files
        if _source_test_name(m["path"]) not in tested_names
        and m.get("exports")
    ]

    untested_list = "\n".join(
        f"- `{m['path']}` — exports: {', '.join(m['exports'][:5])}"
        for m in untested[:20]
    )

    body = f"""\
Identify test coverage gaps in this codebase.

## Test Statistics
- Source modules: {len(source_files)}
- Test modules: {len(test_files)}
- Modules with no matching test file: {len(untested)}

## Untested Modules (no corresponding test file found)
{untested_list or '- All modules appear to have test files'}

## What to Check
1. **Missing test files**: Which modules have zero tests?
2. **Thin tests**: Tests that exist but only cover the happy path
3. **Error path coverage**: Are error handlers and edge cases tested?
4. **Integration gaps**: Are module boundaries tested (not just units)?
5. **Critical paths**: Are authentication, payment, data mutation flows tested?

For each gap:
- Module and function that needs testing
- What test scenarios are missing
- Priority (Critical/High/Medium) based on module importance
"""
    return AnalysisPrompt(
        prompt_type="test-gaps",
        title="Test Coverage Gaps",
        body=body,
        files=[m["path"] for m in untested[:15]],
    )


def _build_performance_prompt(ctx: dict) -> AnalysisPrompt:
    """Performance bottlenecks prompt."""
    modules = ctx["modules"]
    ast_symbols = ctx["ast_symbols"]

    # Find complex functions via analysis module
    complexity_lines: list[str] = []
    try:
        from .analysis import analyze_complexity

        # Read file contents for complexity analysis
        root = Path(ctx["repo_map"].get("root", "."))
        file_contents: dict[str, str] = {}
        for m in modules[:50]:
            fpath = root / m["path"]
            if fpath.exists() and fpath.stat().st_size < 100_000:
                try:
                    file_contents[m["path"]] = fpath.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    pass  # File unreadable — skip from complexity analysis
        report = analyze_complexity(file_contents)
        # Top 10 most complex
        for mc in report.modules[:10]:
            complexity_lines.append(
                f"- `{mc.file}` — avg complexity {mc.avg_complexity}, "
                f"max {mc.max_complexity} (`{mc.most_complex}`)"
            )
    except (ImportError, OSError, ValueError):
        # ImportError: analysis module; OSError: file read; ValueError: parse errors
        logger.debug("Complexity analysis unavailable")

    complexity_text = "\n".join(complexity_lines) if complexity_lines else "- Complexity analysis unavailable"

    body = f"""\
Analyze this codebase for performance bottlenecks.

## High-Complexity Functions (potential hotspots)
{complexity_text}

## What to Check
1. **N+1 queries**: Database calls inside loops
2. **Missing caching**: Repeated expensive computations
3. **Blocking I/O**: Synchronous file/network operations in async contexts
4. **Memory leaks**: Unbounded caches, event listener accumulation
5. **Algorithm complexity**: O(n^2) or worse in hot paths
6. **Large payloads**: Unnecessary data fetching, missing pagination

For each bottleneck:
- File and function
- Expected performance impact (latency/memory/CPU)
- Optimization suggestion with complexity tradeoff
"""
    return AnalysisPrompt(
        prompt_type="performance",
        title="Performance Bottlenecks",
        body=body,
        files=[mc.file for mc in (report.modules[:10] if complexity_lines else [])],
    )


def _build_deps_prompt(ctx: dict) -> AnalysisPrompt:
    """Dependency risks prompt."""
    dep_health = ctx["dep_health"]
    repo_map = ctx["repo_map"]

    dep_lines: list[str] = []
    if dep_health:
        if dep_health.outdated:
            dep_lines.append("## Outdated Dependencies")
            for d in dep_health.outdated[:10]:
                dep_lines.append(
                    f"- `{d.name}` current={d.current_version} latest={d.latest_version}"
                )
        if dep_health.duplicates:
            dep_lines.append("\n## Duplicate Dependencies")
            for d in dep_health.duplicates[:10]:
                dep_lines.append(f"- `{d.name}` versions: {', '.join(d.versions)}")
        if dep_health.license_conflicts:
            dep_lines.append("\n## License Conflicts")
            for lc in dep_health.license_conflicts[:10]:
                dep_lines.append(f"- `{lc.name}` license={lc.license}")

    config_files = repo_map.get("config_files", [])
    manifest_files = [f for f in config_files if any(
        f.endswith(n)
        for n in ("package.json", "requirements.txt", "go.mod", "Cargo.toml",
                   "pyproject.toml", "pom.xml", "build.gradle", "Gemfile")
    )]

    body = f"""\
Review the dependency landscape of this codebase for risks.

## Manifest Files
{chr(10).join(f'- `{f}`' for f in manifest_files) or '- None detected'}

{chr(10).join(dep_lines) if dep_lines else '## Note: Automated dep health data unavailable — review manifests manually'}

## What to Check
1. **Outdated deps**: Major version behind, known CVEs
2. **Abandoned deps**: No commits in >1 year, archived repos
3. **License compliance**: Incompatible licenses (GPL in MIT project, etc.)
4. **Duplicate deps**: Same functionality from multiple packages
5. **Phantom deps**: Used in code but not declared in manifest
6. **Heavy deps**: Large packages imported for a single utility function
7. **Supply chain**: Typosquatting risks, single-maintainer packages

For each risk:
- Package name and version
- Risk type and severity
- Recommended action (update/replace/remove)
"""
    return AnalysisPrompt(
        prompt_type="deps",
        title="Dependency Risks",
        body=body,
        files=manifest_files[:10],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_test_module(path: str) -> bool:
    """Check if a file path is a test file."""
    name = path.split("/")[-1]
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith("_test.go")
        or name.endswith(".test.ts")
        or name.endswith(".test.tsx")
        or name.endswith(".test.js")
        or name.endswith(".test.jsx")
        or name.endswith(".spec.ts")
        or name.endswith(".spec.js")
        or "/tests/" in path
        or "/__tests__/" in path
    )


def _test_target_name(path: str) -> str:
    """Extract the target module name from a test file path."""
    name = path.split("/")[-1]
    # test_foo.py -> foo
    if name.startswith("test_"):
        return name.replace("test_", "", 1).rsplit(".", 1)[0]
    # foo_test.py -> foo
    for suffix in ("_test.py", "_test.go", ".test.ts", ".test.tsx",
                    ".test.js", ".test.jsx", ".spec.ts", ".spec.js"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name.rsplit(".", 1)[0]


def _source_test_name(path: str) -> str:
    """Extract the module name from a source file to match against test names."""
    name = path.split("/")[-1]
    return name.rsplit(".", 1)[0]


# ---------------------------------------------------------------------------
# Builder registry
# ---------------------------------------------------------------------------

_BUILDERS = {
    "solid": _build_solid_prompt,
    "dead-code": _build_dead_code_prompt,
    "security": _build_security_prompt,
    "architecture": _build_architecture_prompt,
    "test-gaps": _build_test_gaps_prompt,
    "performance": _build_performance_prompt,
    "deps": _build_deps_prompt,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_prompts(
    workspace: str,
    types: list[str] | None = None,
) -> list[AnalysisPrompt]:
    """Generate analysis prompts from scanned codebase data.

    Args:
        workspace: Path to the repo root.
        types: List of prompt types to generate. None = all.

    Returns:
        List of AnalysisPrompt objects.
    """
    selected = types or list(PROMPT_TYPES)

    # Validate types
    invalid = [t for t in selected if t not in _BUILDERS]
    if invalid:
        raise ValueError(f"Unknown prompt type(s): {', '.join(invalid)}. Valid: {', '.join(PROMPT_TYPES)}")

    ctx = _gather_context(workspace)

    prompts: list[AnalysisPrompt] = []
    for ptype in selected:
        builder = _BUILDERS[ptype]
        try:
            prompt = builder(ctx)
            prompts.append(prompt)
        except (ValueError, KeyError, TypeError) as exc:
            # Prompt builder data access or formatting errors
            logger.warning("Failed to build %s prompt: %s", ptype, exc)

    return prompts


def render_prompts_markdown(prompts: list[AnalysisPrompt]) -> str:
    """Render prompts as a single markdown document."""
    lines = ["# Analysis Prompts", ""]
    lines.append(
        "Generated by RepoForge. Copy any prompt below into your LLM for targeted analysis."
    )
    lines.append("")

    for i, p in enumerate(prompts, 1):
        lines.append(f"---")
        lines.append(f"")
        lines.append(f"## {i}. {p.title}")
        lines.append("")
        lines.append(p.body)
        lines.append("")

    return "\n".join(lines)


def write_individual_prompts(prompts: list[AnalysisPrompt], output_dir: str) -> list[str]:
    """Write each prompt as a separate .txt file.

    Returns list of written file paths.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for p in prompts:
        filename = f"{p.prompt_type}.txt"
        filepath = out / filename
        filepath.write_text(p.body, encoding="utf-8")
        written.append(str(filepath))

    return written
