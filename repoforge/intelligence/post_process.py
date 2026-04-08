"""
post_process.py — Deterministic post-processing for generated documentation.

Stage D of the two-stage verification pipeline.
Applies rule-based corrections that don't need an LLM:
  1. Port replacement (wrong ports → real port from facts)
  2. Version replacement (wrong Go/project version → real version)
  3. URL placeholder cleanup (yourusername → real module path)
  4. Endpoint validation (flag endpoints not in facts)
  5. Missing fact injection (append missing endpoints/tables)
  6. Dependency validation (flag deps not in build files)
  7. Code block validation (flag fabricated function definitions)

All corrections are logged for audit.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from ..facts import FactItem
from .ast_extractor import ASTSymbol
from .build_parser import BuildInfo

logger = logging.getLogger(__name__)


@dataclass
class Correction:
    """A single deterministic correction applied to chapter content."""

    original: str
    corrected: str
    reason: str
    line: int | None


def post_process_chapter(
    content: str,
    facts: list[FactItem],
    build_info: BuildInfo | None,
    ast_symbols: dict[str, list[ASTSymbol]] | None,
    chapter_file: str = "",
) -> tuple[str, list[Correction]]:
    """Apply deterministic corrections to a generated documentation chapter.

    Runs eight correction passes in order:
      0. Chain-of-thought stripping (remove LLM "thinking" preamble)
      1. Port replacement
      2. Version replacement
      3. URL placeholder cleanup
      4. Endpoint validation (comments only, no removal)
      5. Missing fact injection (api-reference / data-models chapters)
      6. Dependency validation (flag deps not in build files)
      7. Code block validation (flag fabricated function definitions)

    Args:
        content: The raw LLM-generated chapter markdown.
        facts: Verified facts extracted from source code.
        build_info: Build metadata (go version, module path, etc.).
        ast_symbols: AST symbols keyed by file path.
        chapter_file: Filename of the chapter (e.g. "06-api-reference.md").

    Returns:
        Tuple of (corrected_content, list_of_corrections).
    """
    corrections: list[Correction] = []

    content = _strip_cot_preamble(content, corrections)
    content = _fix_ports(content, facts, corrections)
    content = _fix_versions(content, build_info, corrections)
    content = _fix_url_placeholders(content, build_info, corrections)
    content = _validate_endpoints(content, facts, corrections)
    content = _inject_missing_facts(content, facts, ast_symbols, chapter_file, corrections)
    content = _fix_dependencies(content, build_info, corrections)
    content = _validate_code_blocks(content, ast_symbols, facts, corrections)

    return content, corrections


# ---------------------------------------------------------------------------
# 0. Chain-of-thought preamble stripping
# ---------------------------------------------------------------------------

# Patterns that match LLM "thinking out loud" lines at the start of output.
# These leak from CLI-based providers (and occasionally API providers) when
# the model reasons before generating the actual document.
_COT_LINE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r'^(?:Now\s+I\s+have|I\s+have\s+(?:all\s+)?(?:the\s+|enough\s+)?(?:information|data|everything|context))', re.IGNORECASE),
    re.compile(r'^(?:Let\s+me\s+(?:write|generate|create|produce|draft|start|begin|now))', re.IGNORECASE),
    re.compile(r'^(?:I\'ll\s+(?:write|generate|create|produce|draft|start|begin|now))', re.IGNORECASE),
    re.compile(r'^(?:I\s+need\s+to\s+(?:write|generate|create|produce|draft))', re.IGNORECASE),
    re.compile(r'^(?:Based\s+on\s+(?:the|this|all|my)\s+.*?(?:I\'ll|let\s+me|I\s+will|I\s+can))', re.IGNORECASE),
    re.compile(r'^(?:OK|Okay|Alright|Right|Sure|Great|Perfect)[,.]?\s+(?:let\s+me|I\'ll|now)', re.IGNORECASE),
    re.compile(r'^(?:Here\s+is|Here\'s)\s+the\s+(?:generated|requested|complete|full|final)', re.IGNORECASE),
    re.compile(r'^(?:Looking\s+at\s+(?:the|this))', re.IGNORECASE),
    re.compile(r'^(?:After\s+(?:reviewing|analyzing|examining|looking))', re.IGNORECASE),
    re.compile(r'^(?:First,?\s+(?:let\s+me|I\'ll|I\s+need))', re.IGNORECASE),
]


def _strip_cot_preamble(
    content: str,
    corrections: list[Correction],
) -> str:
    """Strip chain-of-thought 'thinking' lines from the beginning of content.

    LLM providers (especially CLI-based ones) sometimes emit reasoning lines
    before the actual markdown document. This function removes those leading
    lines, stopping as soon as it hits a markdown heading or real content.
    """
    lines = content.split("\n")
    stripped_count = 0
    cot_count = 0  # Track actual CoT lines (not just blank lines)

    for line in lines:
        stripped_line = line.strip()

        # Empty lines at the start are safe to skip (but only if we find CoT after)
        if not stripped_line:
            stripped_count += 1
            continue

        # Stop at markdown headings — that's real content
        if stripped_line.startswith("#"):
            break

        # Stop at markdown structural elements (lists, tables, code blocks, etc.)
        if stripped_line.startswith(("- ", "* ", "1.", "|", "```", "---", ">")):
            break

        # Check if this line matches a CoT pattern
        is_cot = any(p.search(stripped_line) for p in _COT_LINE_PATTERNS)
        if is_cot:
            stripped_count += 1
            cot_count += 1
            continue

        # Non-empty, non-CoT, non-heading line — stop stripping
        break

    # Only apply stripping if we actually found CoT lines (not just blank lines)
    if cot_count > 0:
        removed_lines = lines[:stripped_count]
        content = "\n".join(lines[stripped_count:]).lstrip("\n")
        corrections.append(Correction(
            original="\n".join(l for l in removed_lines if l.strip()),
            corrected="[removed]",
            reason=f"Stripped {stripped_count} chain-of-thought preamble line(s) from LLM output",
            line=1,
        ))

    return content


# ---------------------------------------------------------------------------
# 1. Port replacement
# ---------------------------------------------------------------------------

# Common wrong ports that LLMs hallucinate
_COMMON_WRONG_PORTS = {"8080", "3000", "5000", "8000", "4000", "9090"}


def _fix_ports(
    content: str,
    facts: list[FactItem],
    corrections: list[Correction],
) -> str:
    """Replace hallucinated ports with the real port from facts."""
    port_facts = [f for f in facts if f.fact_type == "port"]
    if not port_facts:
        return content

    real_port = port_facts[0].value

    # Replace ENGRAM_PORT placeholder ONLY in URL/port contexts (e.g. :ENGRAM_PORT)
    # NOT when it appears as an env var name (e.g. export ENGRAM_PORT=...)
    _engram_port_pattern = re.compile(r'(?<=:)ENGRAM_PORT\b')
    if _engram_port_pattern.search(content):
        old = content
        content = _engram_port_pattern.sub(real_port, content)
        if content != old:
            corrections.append(Correction(
                original="ENGRAM_PORT",
                corrected=real_port,
                reason=f"Replaced ENGRAM_PORT placeholder with actual port {real_port}",
                line=None,
            ))

    # Replace common wrong ports
    for wrong_port in _COMMON_WRONG_PORTS:
        if wrong_port == real_port:
            continue
        # Match port in URL-like contexts: :PORT, port PORT, localhost:PORT, VAR=PORT
        pattern = re.compile(
            r'(?<=[:\s=])' + re.escape(wrong_port) + r'(?=[/\s\)\]\}\"`\'$,]|$)',
            re.MULTILINE,
        )
        if pattern.search(content):
            new_content = pattern.sub(real_port, content)
            if new_content != content:
                corrections.append(Correction(
                    original=wrong_port,
                    corrected=real_port,
                    reason=f"Replaced hallucinated port {wrong_port} with real port {real_port} (from {port_facts[0].file}:{port_facts[0].line})",
                    line=None,
                ))
                content = new_content

    return content


# ---------------------------------------------------------------------------
# 2. Version replacement
# ---------------------------------------------------------------------------

_GO_VERSION_PATTERN = re.compile(r'Go\s+1\.(\d+)(?:\.\d+)?')
_PROJECT_VERSION_PATTERN = re.compile(r'[vV]ersion\s+["\']?(\d+\.\d+(?:\.\d+)?)')


def _fix_versions(
    content: str,
    build_info: BuildInfo | None,
    corrections: list[Correction],
) -> str:
    """Replace wrong Go/project versions with real ones from build_info."""
    if not build_info:
        return content

    # Fix Go version
    if build_info.go_version:
        real_go = build_info.go_version  # e.g. "1.23" or "1.23.0"

        def _replace_go_version(m: re.Match) -> str:
            old_ver = m.group(0)
            new_ver = f"Go {real_go}"
            if old_ver != new_ver:
                corrections.append(Correction(
                    original=old_ver,
                    corrected=new_ver,
                    reason=f"Replaced wrong Go version with real version from go.mod",
                    line=None,
                ))
            return new_ver

        content = _GO_VERSION_PATTERN.sub(_replace_go_version, content)

    # Fix project version
    if build_info.version:
        real_ver = build_info.version

        def _replace_project_version(m: re.Match) -> str:
            found_ver = m.group(1)
            if found_ver != real_ver:
                full_old = m.group(0)
                full_new = full_old.replace(found_ver, real_ver)
                corrections.append(Correction(
                    original=full_old,
                    corrected=full_new,
                    reason=f"Replaced wrong project version {found_ver} with {real_ver}",
                    line=None,
                ))
                return full_new
            return m.group(0)

        content = _PROJECT_VERSION_PATTERN.sub(_replace_project_version, content)

    return content


# ---------------------------------------------------------------------------
# 3. URL placeholder cleanup
# ---------------------------------------------------------------------------

_URL_PLACEHOLDER_PATTERNS = [
    (re.compile(r'(git\s+clone\s+https?://github\.com/)yourusername(/\S+)', re.IGNORECASE), "yourusername"),
    (re.compile(r'(git\s+clone\s+https?://github\.com/)your-username(/\S+)', re.IGNORECASE), "your-username"),
    (re.compile(r'(https?://github\.com/)yourusername(/\S+)', re.IGNORECASE), "yourusername"),
    (re.compile(r'(https?://github\.com/)your-username(/\S+)', re.IGNORECASE), "your-username"),
]


def _fix_url_placeholders(
    content: str,
    build_info: BuildInfo | None,
    corrections: list[Correction],
) -> str:
    """Replace yourusername/your-username in clone URLs with real module path."""
    if not build_info or not build_info.module_path:
        return content

    module_path = build_info.module_path
    # Extract org/repo from module path like "github.com/Org/Repo"
    parts = module_path.split("/")
    if len(parts) >= 3 and "github.com" in parts[0]:
        real_owner = parts[1]
    elif len(parts) >= 2:
        real_owner = parts[-2]
    else:
        return content

    for pattern, placeholder in _URL_PLACEHOLDER_PATTERNS:
        if pattern.search(content):
            new_content = pattern.sub(rf'\g<1>{real_owner}\g<2>', content)
            if new_content != content:
                corrections.append(Correction(
                    original=placeholder,
                    corrected=real_owner,
                    reason=f"Replaced URL placeholder '{placeholder}' with '{real_owner}' from module path",
                    line=None,
                ))
                content = new_content

    return content


# ---------------------------------------------------------------------------
# 4. Endpoint validation
# ---------------------------------------------------------------------------

# Pattern 1: HTTP method prefix — e.g. "GET /health", "POST /api/observations"
_ENDPOINT_METHOD_PATTERN = re.compile(
    r'(?:GET|POST|PUT|DELETE|PATCH)\s+(/[a-zA-Z0-9_/\-\{\}:\.]+)',
    re.IGNORECASE,
)

# Pattern 2: Bare API route — e.g. `/api/memory`, `/v1/users`, `/v2/sync`
# Only matches paths that start with /api/ or /v followed by a digit.
# Negative lookbehind avoids matching inside longer paths like file references.
_BARE_API_ROUTE_PATTERN = re.compile(
    r'(?<![a-zA-Z0-9_\-\.])(/(?:api|v\d+)/[a-zA-Z0-9_/\-\{\}:\.]+)',
)

# File-path extensions — if a matched route ends with one of these, skip it.
_FILE_EXTENSIONS = frozenset({
    ".go", ".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".java", ".rb",
    ".c", ".h", ".cpp", ".hpp", ".css", ".scss", ".html", ".json",
    ".yaml", ".yml", ".toml", ".xml", ".md", ".txt", ".sh", ".sql",
    ".proto", ".graphql", ".mod", ".sum", ".lock", ".cfg", ".ini",
})


def _looks_like_file_path(path: str) -> bool:
    """Return True if the path looks like a file/directory reference, not an API route."""
    # Has a file extension
    for ext in _FILE_EXTENSIONS:
        if path.endswith(ext):
            return True
    # Contains typical source directory segments (e.g. /internal/store/, /cmd/engram/)
    _dir_segments = {"internal", "cmd", "pkg", "src", "lib", "vendor", "node_modules", "dist", "build"}
    parts = [p for p in path.split("/") if p]
    if parts and parts[0] in _dir_segments:
        return True
    return False


def _normalize_fact_paths(endpoint_facts: set[str]) -> set[str]:
    """Extract and normalize just the path portion from endpoint fact values."""
    fact_paths: set[str] = set()
    for ep in endpoint_facts:
        # Facts may be "GET /health" or just "/health"
        parts = ep.strip().split()
        path = parts[-1] if parts else ep
        fact_paths.add(path.strip())
    return fact_paths


def _path_matches_facts(path: str, fact_paths: set[str]) -> bool:
    """Check if a path matches any known endpoint, with normalization.

    Handles:
      - Exact match: /observations == /observations
      - Trailing slash: /observations/ == /observations
      - Path params: /sessions/{id}/end matches /sessions/:id/end
      - Prefix match: /api/observations matches fact /observations
    """
    normalized = path.strip().rstrip("/")
    if not normalized:
        return False

    # Normalize path params: replace {param} and :param with a placeholder
    def _normalize_params(p: str) -> str:
        p = re.sub(r'\{[^}]+\}', ':param', p)
        p = re.sub(r':([a-zA-Z_]\w*)', ':param', p)
        return p

    normalized_param = _normalize_params(normalized)

    for fp in fact_paths:
        fp_clean = fp.rstrip("/")
        fp_param = _normalize_params(fp_clean)
        # Exact match (with or without param normalization)
        if normalized == fp_clean or normalized_param == fp_param:
            return True
        # The content path is a sub-path or prefixed variant of a fact path
        # e.g. content has /api/observations, fact has /observations
        if fp_clean and normalized.endswith(fp_clean):
            return True
        if normalized and fp_clean.endswith(normalized):
            return True
    return False


def _validate_endpoints(
    content: str,
    facts: list[FactItem],
    corrections: list[Correction],
) -> str:
    """Flag endpoint mentions in content that are NOT in the verified facts.

    Catches two patterns:
      1. HTTP method prefixed routes: GET /health, POST /api/observations
      2. Bare API routes: /api/memory, /v1/users (only /api/* and /v{N}/* prefixes)

    Does NOT remove them (too risky) — adds an HTML comment instead.
    Skips file paths and directory references.
    """
    endpoint_facts = {f.value for f in facts if f.fact_type == "endpoint"}
    if not endpoint_facts:
        return content

    fact_paths = _normalize_fact_paths(endpoint_facts)

    lines = content.split("\n")
    new_lines: list[str] = []

    for i, line in enumerate(lines):
        if "<!-- UNVERIFIED" in line:
            new_lines.append(line)
            continue

        unverified: list[str] = []

        # Pass 1: HTTP method prefixed endpoints
        for endpoint_path in _ENDPOINT_METHOD_PATTERN.findall(line):
            if _looks_like_file_path(endpoint_path):
                continue
            if not _path_matches_facts(endpoint_path, fact_paths):
                unverified.append(endpoint_path)

        # Pass 2: Bare API routes (/api/... and /v{N}/...)
        for endpoint_path in _BARE_API_ROUTE_PATTERN.findall(line):
            if _looks_like_file_path(endpoint_path):
                continue
            # Skip if already caught by method pattern on same line
            if endpoint_path in unverified:
                continue
            if not _path_matches_facts(endpoint_path, fact_paths):
                unverified.append(endpoint_path)

        for ep in unverified:
            corrections.append(Correction(
                original=ep,
                corrected=ep,
                reason=f"Endpoint {ep} not found in verified facts — may be hallucinated",
                line=i + 1,
            ))

        new_lines.append(line)
        if unverified:
            ep_list = ", ".join(unverified)
            new_lines.append(
                f"<!-- UNVERIFIED ENDPOINT: {ep_list} not found in extracted endpoints -->"
            )

    return "\n".join(new_lines)


# ---------------------------------------------------------------------------
# 5. Missing fact injection
# ---------------------------------------------------------------------------

def _inject_missing_facts(
    content: str,
    facts: list[FactItem],
    ast_symbols: dict[str, list[ASTSymbol]] | None,
    chapter_file: str,
    corrections: list[Correction],
) -> str:
    """Append missing endpoints or data models if the chapter is api-reference or data-models."""
    chapter_lower = chapter_file.lower()

    if "api-reference" in chapter_lower or "api_reference" in chapter_lower:
        content = _inject_missing_endpoints(content, facts, corrections)
    elif "data-model" in chapter_lower or "data_model" in chapter_lower:
        content = _inject_missing_tables(content, facts, ast_symbols, corrections)

    return content


def _inject_missing_endpoints(
    content: str,
    facts: list[FactItem],
    corrections: list[Correction],
) -> str:
    """Append endpoints from facts that are not mentioned in the content."""
    endpoint_facts = [f for f in facts if f.fact_type == "endpoint"]
    if not endpoint_facts:
        return content

    content_lower = content.lower()
    missing: list[FactItem] = []

    for fact in endpoint_facts:
        # Check if the endpoint path appears anywhere in the content
        parts = fact.value.strip().split()
        path = parts[-1] if parts else fact.value
        if path.lower() not in content_lower:
            missing.append(fact)

    if not missing:
        return content

    section = "\n\n## Additional Endpoints\n\n"
    section += "> The following endpoints were found in the source code but not covered above.\n\n"
    for fact in missing:
        section += f"- `{fact.value}` — found in `{fact.file}` (line {fact.line})\n"

    corrections.append(Correction(
        original="",
        corrected=f"[+{len(missing)} missing endpoints]",
        reason=f"Injected {len(missing)} endpoint(s) found in source but missing from chapter",
        line=None,
    ))

    return content.rstrip() + "\n" + section


def _inject_missing_tables(
    content: str,
    facts: list[FactItem],
    ast_symbols: dict[str, list[ASTSymbol]] | None,
    corrections: list[Correction],
) -> str:
    """Append database tables from facts that are not mentioned in the content."""
    db_facts = [f for f in facts if f.fact_type == "db_table"]
    if not db_facts:
        return content

    content_lower = content.lower()
    missing: list[FactItem] = []

    for fact in db_facts:
        table_name = fact.value.strip()
        if table_name.lower() not in content_lower:
            missing.append(fact)

    if not missing:
        return content

    section = "\n\n## Additional Data Tables\n\n"
    section += "> The following tables were found in the source code but not covered above.\n\n"
    for fact in missing:
        section += f"- `{fact.value}` — defined in `{fact.file}` (line {fact.line})\n"

    corrections.append(Correction(
        original="",
        corrected=f"[+{len(missing)} missing tables]",
        reason=f"Injected {len(missing)} table(s) found in source but missing from chapter",
        line=None,
    ))

    return content.rstrip() + "\n" + section


# ---------------------------------------------------------------------------
# 6. Dependency validation
# ---------------------------------------------------------------------------

# Go standard library top-level packages (not exhaustive, but covers the common ones
# that LLMs reference). We match against the first path segment.
_GO_STDLIB_PACKAGES: frozenset[str] = frozenset({
    "archive", "bufio", "builtin", "bytes", "cmp", "compress", "container",
    "context", "crypto", "database", "debug", "embed", "encoding", "errors",
    "expvar", "flag", "fmt", "go", "hash", "html", "image", "index", "io",
    "iter", "log", "maps", "math", "mime", "net", "os", "path", "plugin",
    "reflect", "regexp", "runtime", "slices", "sort", "strconv", "strings",
    "structs", "sync", "syscall", "testing", "text", "time", "unicode",
    "unsafe", "internal", "vendor",
})

# Patterns to extract dependency-like references from markdown content.
# Full GitHub/GitLab paths: github.com/org/repo or github.com/org/repo/sub
_GITHUB_DEP_PATTERN = re.compile(
    r'(?:github\.com|gitlab\.com|bitbucket\.org)/[\w\-\.]+/[\w\-\.]+(?:/[\w\-\.]+)*'
)

# npm scoped packages: @scope/package
_NPM_SCOPED_PATTERN = re.compile(r'@[\w\-]+/[\w\-]+')

# Python package references in pip install / import statements
_PIP_INSTALL_PATTERN = re.compile(r'pip\s+install\s+(?:-[\w]+\s+)*(\S+)')


def _fix_dependencies(
    content: str,
    build_info: BuildInfo | None,
    corrections: list[Correction],
) -> str:
    """Flag dependency claims in content that are NOT in the real dependency list.

    Conservative approach: only flags full module paths (github.com/org/repo)
    that clearly don't appear in build_info.dependencies. Does NOT flag
    standard library packages or short ambiguous names.
    """
    if not build_info or not build_info.dependencies:
        return content

    real_deps = set(build_info.dependencies)
    # Also include dev deps as valid (they're real, just not production)
    real_deps.update(build_info.dev_dependencies)
    # The project's own module path is not a dependency but references to it are valid
    if build_info.module_path:
        real_deps.add(build_info.module_path)

    # Build a lowercase lookup for case-insensitive matching
    real_deps_lower = {d.lower() for d in real_deps}

    claimed_deps = _extract_claimed_deps(content, build_info.language)

    if not claimed_deps:
        return content

    lines = content.split("\n")
    new_lines: list[str] = []

    for i, line in enumerate(lines):
        flagged_deps: list[str] = []
        for dep in sorted(claimed_deps):
            if dep not in line:
                continue
            if _is_real_dep(dep, real_deps, real_deps_lower, build_info.language):
                continue
            if _is_stdlib(dep, build_info.language):
                continue
            # It's in this line and NOT a real dep — flag it
            flagged_deps.append(dep)

        new_lines.append(line)
        if flagged_deps and "<!-- UNVERIFIED DEP" not in line:
            for dep in flagged_deps:
                corrections.append(Correction(
                    original=dep,
                    corrected=dep,
                    reason=f"Dependency {dep} not found in project dependencies — may be hallucinated",
                    line=i + 1,
                ))
            dep_list = ", ".join(flagged_deps)
            new_lines.append(
                f"<!-- UNVERIFIED DEPENDENCY: {dep_list} — not found in project build files -->"
            )

    return "\n".join(new_lines)


def _extract_claimed_deps(content: str, language: str) -> set[str]:
    """Extract dependency-like references from chapter content."""
    claimed: set[str] = set()

    # Full paths (github.com/org/repo) — works for Go, Rust, etc.
    for m in _GITHUB_DEP_PATTERN.finditer(content):
        # Normalize: take up to org/repo (first 3 segments)
        parts = m.group(0).split("/")
        if len(parts) >= 3:
            # Store the canonical 3-segment form (github.com/org/repo)
            claimed.add("/".join(parts[:3]))

    # npm scoped packages
    if language in ("typescript", "javascript"):
        for m in _NPM_SCOPED_PATTERN.finditer(content):
            claimed.add(m.group(0))

    # pip install targets
    if language == "python":
        for m in _PIP_INSTALL_PATTERN.finditer(content):
            pkg = m.group(1).strip()
            # Strip version specifiers
            pkg = re.split(r'[>=<!\[;]', pkg)[0].strip()
            if pkg and not pkg.startswith("-"):
                claimed.add(pkg)

    return claimed


def _is_real_dep(
    dep: str,
    real_deps: set[str],
    real_deps_lower: set[str],
    language: str,
) -> bool:
    """Check if a claimed dep matches any real dependency."""
    # Exact match
    if dep in real_deps:
        return True
    if dep.lower() in real_deps_lower:
        return True

    # For Go: github.com/org/repo/subpkg should match github.com/org/repo
    # And github.com/org/repo should match github.com/org/repo/v2
    for real in real_deps:
        # Claimed is a sub-path of a real dep
        if dep.startswith(real + "/") or dep.startswith(real):
            return True
        # Real dep is a sub-path of claimed (e.g. real has /v2 suffix)
        if real.startswith(dep + "/") or real.startswith(dep):
            return True

    return False


def _is_stdlib(dep: str, language: str) -> bool:
    """Check if a dependency reference is a standard library package."""
    if language == "go":
        # Go stdlib: net/http, database/sql, fmt, os, etc.
        # These don't have a domain prefix (no github.com/)
        if "/" in dep:
            top = dep.split("/")[0]
            # If the top-level is a known Go stdlib package and NOT a domain
            if top in _GO_STDLIB_PACKAGES and "." not in top:
                return True
        else:
            if dep in _GO_STDLIB_PACKAGES:
                return True
    # Python stdlib is hard to enumerate — we only flag pip install targets,
    # which are unlikely to be stdlib.
    # Node stdlib (fs, path, http) won't match our patterns.
    return False


# ---------------------------------------------------------------------------
# 7. Code block validation — flag fabricated function definitions
# ---------------------------------------------------------------------------

# Patterns that match function/method DEFINITIONS inside code blocks.
# Only definitions (not calls) — conservative to avoid false positives.
_CODE_BLOCK_FUNC_DEF_PATTERNS = [
    re.compile(r'\bfunc\s+(?:\([^)]*\)\s+)?(\w+)\s*\('),   # Go: func Name( or func (r *R) Name(
    re.compile(r'\bdef\s+(\w+)\s*\('),                       # Python: def name(
    re.compile(r'\bfunction\s+(\w+)\s*\('),                   # JS/TS: function name(
    re.compile(r'\b(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{'),    # JS/TS: name() { or async name() {
]


def _build_known_symbols(
    ast_symbols: dict[str, list[ASTSymbol]] | None,
    facts: list[FactItem],
) -> set[str]:
    """Collect all known function/method names from AST symbols and facts."""
    known: set[str] = set()
    if ast_symbols:
        for symbols in ast_symbols.values():
            for sym in symbols:
                known.add(sym.name)
    for fact in facts:
        # Fact values may contain function names in various formats
        val = fact.value.strip()
        if val:
            # Extract last word-like token as potential function name
            parts = re.split(r'[\s/\.:]+', val)
            for part in parts:
                if re.match(r'^[a-zA-Z_]\w*$', part):
                    known.add(part)
    return known


def _validate_code_blocks(
    content: str,
    ast_symbols: dict[str, list[ASTSymbol]] | None,
    facts: list[FactItem],
    corrections: list[Correction],
) -> str:
    """Flag function definitions in code blocks that don't exist in the codebase.

    Only checks function DEFINITIONS (not calls) inside fenced code blocks.
    Appends an HTML comment after the code block for each unverified function.
    """
    if not ast_symbols and not facts:
        return content

    known = _build_known_symbols(ast_symbols, facts)
    if not known:
        return content

    # Split content into code-block and non-code-block segments
    # Pattern matches fenced code blocks: ```...```
    _fence_pattern = re.compile(r'^```[^\n]*\n(.*?)^```', re.MULTILINE | re.DOTALL)

    result_parts: list[str] = []
    last_end = 0

    for match in _fence_pattern.finditer(content):
        # Add text before this code block
        result_parts.append(content[last_end:match.start()])

        block_code = match.group(1)
        block_full = match.group(0)

        # Extract function definitions from this code block
        unverified: list[str] = []
        for pattern in _CODE_BLOCK_FUNC_DEF_PATTERNS:
            for func_match in pattern.finditer(block_code):
                func_name = func_match.group(1)
                # Skip very common/generic names that are likely fine
                if func_name in ("main", "init", "setup", "test", "run", "new", "New"):
                    continue
                if func_name not in known:
                    unverified.append(func_name)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_unverified: list[str] = []
        for name in unverified:
            if name not in seen:
                seen.add(name)
                unique_unverified.append(name)

        result_parts.append(block_full)
        for func_name in unique_unverified:
            corrections.append(Correction(
                original=func_name,
                corrected=func_name,
                reason=f"Code block function '{func_name}' not found in codebase — may be fabricated",
                line=None,
            ))
            result_parts.append(
                f"\n<!-- UNVERIFIED CODE: {func_name} not found in codebase -->"
            )

        last_end = match.end()

    # Add remaining content after last code block
    result_parts.append(content[last_end:])

    return "".join(result_parts)
