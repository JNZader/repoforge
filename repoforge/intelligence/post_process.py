"""
post_process.py — Deterministic post-processing for generated documentation.

Stage D of the two-stage verification pipeline.
Applies rule-based corrections that don't need an LLM:
  1. Port replacement (wrong ports → real port from facts)
  2. Version replacement (wrong Go/project version → real version)
  3. URL placeholder cleanup (yourusername → real module path)
  4. Endpoint validation (flag endpoints not in facts)
  5. Missing fact injection (append missing endpoints/tables)

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

    Runs five correction passes in order:
      1. Port replacement
      2. Version replacement
      3. URL placeholder cleanup
      4. Endpoint validation (comments only, no removal)
      5. Missing fact injection (api-reference / data-models chapters)

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

    content = _fix_ports(content, facts, corrections)
    content = _fix_versions(content, build_info, corrections)
    content = _fix_url_placeholders(content, build_info, corrections)
    content = _validate_endpoints(content, facts, corrections)
    content = _inject_missing_facts(content, facts, ast_symbols, chapter_file, corrections)

    return content, corrections


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

    # Replace ENGRAM_PORT placeholder in curl examples
    if "ENGRAM_PORT" in content:
        old = content
        content = content.replace("ENGRAM_PORT", real_port)
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
        # Match port in URL-like contexts: :PORT, port PORT, localhost:PORT
        pattern = re.compile(
            r'(?<=[:\s])' + re.escape(wrong_port) + r'(?=[/\s\)\]\}\"`\'$,]|$)',
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

_ENDPOINT_MENTION_PATTERN = re.compile(
    r'(?:GET|POST|PUT|DELETE|PATCH)\s+(/[a-zA-Z0-9_/\-\{\}:\.]+)',
    re.IGNORECASE,
)


def _validate_endpoints(
    content: str,
    facts: list[FactItem],
    corrections: list[Correction],
) -> str:
    """Flag endpoint mentions in content that are NOT in the verified facts.

    Does NOT remove them (too risky) — adds an HTML comment instead.
    """
    endpoint_facts = {f.value for f in facts if f.fact_type == "endpoint"}
    if not endpoint_facts:
        return content

    # Normalize fact endpoints: extract just the path part
    fact_paths: set[str] = set()
    for ep in endpoint_facts:
        # Facts may be "GET /health" or just "/health"
        parts = ep.strip().split()
        path = parts[-1] if parts else ep
        fact_paths.add(path.strip())

    lines = content.split("\n")
    new_lines: list[str] = []

    for i, line in enumerate(lines):
        matches = _ENDPOINT_MENTION_PATTERN.findall(line)
        flagged = False
        for endpoint_path in matches:
            normalized = endpoint_path.strip().rstrip("/")
            if normalized and normalized not in fact_paths:
                # Check with different normalizations
                if not any(normalized == fp.rstrip("/") for fp in fact_paths):
                    if "<!-- UNVERIFIED" not in line:
                        corrections.append(Correction(
                            original=endpoint_path,
                            corrected=endpoint_path,
                            reason=f"Endpoint {endpoint_path} not found in verified facts — may be hallucinated",
                            line=i + 1,
                        ))
                        flagged = True

        new_lines.append(line)
        if flagged:
            new_lines.append(f"<!-- UNVERIFIED ENDPOINT(S) on line above — not found in source code facts -->")

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
