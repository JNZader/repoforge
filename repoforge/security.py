"""
security.py - Security scanner for generated skills and documentation.

Scans markdown output for security issues across 5 categories:
  1. Prompt Injection — identity override, system prompt leaks, control tokens
  2. Secrets         — AWS keys, GitHub tokens, API keys, hardcoded passwords
  3. PII             — email addresses, SSNs, phone numbers
  4. Destructive     — rm -rf /, DROP TABLE, force push to main, fork bombs
  5. Unsafe Code     — eval(), exec(), os.system(), pickle.loads()

Works standalone: purely regex-based, no LLM calls needed.
Context-aware: patterns inside Anti-Patterns sections are downgraded to INFO.

Inspired by:
  - universal-skills-manager (20+ detection categories)
  - NVIDIA/garak (LLM vulnerability scanner)
  - claude-code-damage-control (patterns.yaml protection)
  - Microsoft agent-governance-toolkit (OWASP Agentic Top 10)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class Severity(Enum):
    CRITICAL = "critical"  # Must fix: secrets, prompt injection
    HIGH = "high"          # Should fix: destructive commands without warnings
    MEDIUM = "medium"      # Consider fixing: unsafe code patterns
    LOW = "low"            # Informational: minor style issues
    INFO = "info"          # FYI: not necessarily a problem


@dataclass
class Finding:
    """A single security finding with location and context."""
    rule_id: str           # e.g. "SEC-001"
    category: str          # prompt_injection, secrets, pii, destructive, unsafe_code
    severity: Severity
    message: str
    file_path: str
    line_number: int
    line_content: str
    suggestion: str = ""


@dataclass
class ScanResult:
    """Aggregated results from scanning one or more files."""
    files_scanned: int
    findings: list[Finding] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.HIGH)

    @property
    def medium_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.MEDIUM)

    @property
    def low_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.LOW)

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.INFO)

    @property
    def passed(self) -> bool:
        """True if no CRITICAL or HIGH findings."""
        return self.critical_count == 0 and self.high_count == 0


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class SecurityScanner:
    """Scans generated markdown files for security issues."""

    # -------------------------------------------------------------------
    # Rule definitions: (regex, rule_id, message)
    # -------------------------------------------------------------------

    PROMPT_INJECTION_PATTERNS: list[tuple[str, str, str]] = [
        (r"ignore\s+(all\s+)?previous\s+instructions",
         "SEC-001", "Prompt injection: ignore instructions"),
        (r"you\s+are\s+now\s+",
         "SEC-002", "Prompt injection: identity override"),
        (r"system\s*:\s*",
         "SEC-003", "Prompt injection: system prompt leak"),
        (r"disregard\s+(all\s+)?(prior|previous|above)",
         "SEC-004", "Prompt injection: disregard prior"),
        (r"forget\s+(everything|all|your)\s+(instructions|rules|training)",
         "SEC-005", "Prompt injection: forget training"),
        (r"act\s+as\s+(if\s+)?(you\s+)?(are|were)\s+",
         "SEC-006", "Prompt injection: role override"),
        (r"<\s*system\s*>",
         "SEC-007", "Prompt injection: system tag"),
        (r"\[INST\]|\[/INST\]|<<SYS>>",
         "SEC-008", "Prompt injection: LLM control tokens"),
    ]

    SECRET_PATTERNS: list[tuple[str, str, str]] = [
        (r"(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}",
         "SEC-010", "AWS Access Key ID"),
        (r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}",
         "SEC-011", "GitHub Personal Access Token"),
        (r"sk-[A-Za-z0-9]{20,}",
         "SEC-012", "OpenAI/Anthropic API Key"),
        (r"(?:password|passwd|pwd)\s*[=:]\s*['\"][^'\"]{8,}",
         "SEC-013", "Hardcoded password"),
        (r"(?:api[_-]?key|apikey)\s*[=:]\s*['\"][^'\"]{8,}",
         "SEC-014", "Hardcoded API key"),
        (r"(?:secret|token)\s*[=:]\s*['\"][^'\"]{8,}",
         "SEC-015", "Hardcoded secret/token"),
        (r"Bearer\s+[A-Za-z0-9\-._~+/]+=*",
         "SEC-016", "Bearer token"),
        (r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
         "SEC-017", "Private key"),
    ]

    PII_PATTERNS: list[tuple[str, str, str]] = [
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
         "SEC-020", "Email address"),
        (r"\b\d{3}[-.]?\d{2}[-.]?\d{4}\b",
         "SEC-021", "Possible SSN"),
        (r"\b(?:\+?1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b",
         "SEC-022", "Phone number"),
    ]

    DESTRUCTIVE_PATTERNS: list[tuple[str, str, str]] = [
        (r"rm\s+-rf\s+[/~]",
         "SEC-030", "Destructive: rm -rf on root/home"),
        (r"rm\s+-rf\s+\*",
         "SEC-031", "Destructive: rm -rf wildcard"),
        (r"DROP\s+(TABLE|DATABASE|SCHEMA)",
         "SEC-032", "Destructive: SQL DROP"),
        (r"TRUNCATE\s+TABLE",
         "SEC-033", "Destructive: SQL TRUNCATE"),
        (r"git\s+push\s+--force\s+origin\s+main",
         "SEC-034", "Destructive: force push to main"),
        (r"chmod\s+777",
         "SEC-035", "Insecure permissions: 777"),
        (r"sudo\s+rm",
         "SEC-036", "Destructive: sudo rm"),
        (r":\(\)\{\s*:\|:&\s*\};:",
         "SEC-037", "Fork bomb"),
        (r"mkfs\.",
         "SEC-038", "Destructive: format filesystem"),
        (r">\s*/dev/sd[a-z]",
         "SEC-039", "Destructive: write to disk device"),
    ]

    UNSAFE_CODE_PATTERNS: list[tuple[str, str, str]] = [
        (r"\beval\s*\(",
         "SEC-040", "Unsafe: eval()"),
        (r"\bexec\s*\(",
         "SEC-041", "Unsafe: exec()"),
        (r"os\.system\s*\(",
         "SEC-042", "Unsafe: os.system()"),
        (r"subprocess\.call\s*\(.*shell\s*=\s*True",
         "SEC-043", "Unsafe: subprocess with shell=True"),
        (r"__import__\s*\(",
         "SEC-044", "Unsafe: dynamic import"),
        (r"pickle\.loads?\s*\(",
         "SEC-045", "Unsafe: pickle deserialization"),
        (r"yaml\.load\s*\([^)]*\)",
         "SEC-046", "Unsafe: yaml.load without SafeLoader"),
        (r"innerHTML\s*=",
         "SEC-047", "Unsafe: innerHTML assignment (XSS risk)"),
    ]

    # Category → severity mapping
    _CATEGORY_SEVERITY: dict[str, Severity] = {
        "prompt_injection": Severity.CRITICAL,
        "secrets": Severity.CRITICAL,
        "pii": Severity.MEDIUM,
        "destructive": Severity.HIGH,
        "unsafe_code": Severity.MEDIUM,
    }

    # Suggestions per category
    _CATEGORY_SUGGESTIONS: dict[str, str] = {
        "prompt_injection": "Remove or rephrase to avoid prompt injection patterns.",
        "secrets": "Replace with environment variable reference (e.g. $API_KEY).",
        "pii": "Replace with placeholder (e.g. user@example.com, 555-0100).",
        "destructive": "Add explicit warning/caution or move to Anti-Patterns section.",
        "unsafe_code": "Use safer alternatives or add a clear warning about risks.",
    }

    def __init__(self, allowlist: list[str] | None = None):
        """Initialize with optional allowlist of rule IDs to skip.

        Args:
            allowlist: List of rule IDs to skip (e.g. ["SEC-020", "SEC-022"]).
        """
        self._allowlist: set[str] = set(allowlist or [])
        self._all_rules = self._build_rules()

    def _build_rules(
        self,
    ) -> list[tuple[re.Pattern, str, str, str, Severity]]:
        """Build compiled rule list: (compiled_regex, rule_id, message, category, severity)."""
        rules: list[tuple[re.Pattern, str, str, str, Severity]] = []

        categories = [
            ("prompt_injection", self.PROMPT_INJECTION_PATTERNS),
            ("secrets", self.SECRET_PATTERNS),
            ("pii", self.PII_PATTERNS),
            ("destructive", self.DESTRUCTIVE_PATTERNS),
            ("unsafe_code", self.UNSAFE_CODE_PATTERNS),
        ]

        for category, patterns in categories:
            severity = self._CATEGORY_SEVERITY[category]
            for regex, rule_id, message in patterns:
                if rule_id not in self._allowlist:
                    compiled = re.compile(regex, re.IGNORECASE)
                    rules.append((compiled, rule_id, message, category, severity))

        return rules

    # -------------------------------------------------------------------
    # Context awareness: Anti-Patterns section detection
    # -------------------------------------------------------------------

    def _is_in_antipattern_context(self, lines: list[str], line_idx: int) -> bool:
        """Check if a line is inside an Anti-Patterns section or a code block
        that's preceded by a clear warning/bad marker.

        Heuristic: walk backwards from line_idx to find the nearest ## heading.
        If it's an Anti-Patterns heading, or if nearby lines contain warning
        signals ("BAD", "Don't", "Warning", "Caution", "NEVER"), return True.
        """
        # Check the surrounding context (up to 15 lines back)
        start = max(0, line_idx - 15)
        context_lines = lines[start:line_idx + 1]
        context = "\n".join(context_lines).lower()

        # Check if we're under an Anti-Patterns heading
        for i in range(line_idx, max(-1, line_idx - 30), -1):
            if i < 0 or i >= len(lines):
                continue
            line = lines[i].strip()
            if re.match(r"^#{1,3}\s+", line):
                # Found a heading — check if it's anti-pattern related
                heading_lower = line.lower()
                if any(kw in heading_lower for kw in [
                    "anti-pattern", "antipattern", "pitfall", "don't", "dont",
                    "bad practice", "bad example", "what not to do", "avoid",
                ]):
                    return True
                # If we hit a non-anti-pattern heading, stop looking
                break

        # Check for warning signals in nearby context
        warning_signals = [
            "# bad", "# don't", "# never", "# avoid", "# wrong",
            "warning", "caution", "danger", "careful",
            "bad -", "bad:", "bad example",
        ]
        return any(signal in context for signal in warning_signals)

    def _get_code_block_ranges(self, lines: list[str]) -> list[tuple[int, int]]:
        """Return list of (start, end) line indices for fenced code blocks."""
        ranges: list[tuple[int, int]] = []
        in_block = False
        block_start = 0

        for i, line in enumerate(lines):
            if line.strip().startswith("```"):
                if not in_block:
                    in_block = True
                    block_start = i
                else:
                    in_block = False
                    ranges.append((block_start, i))

        return ranges

    def _is_in_code_block(
        self, line_idx: int, code_ranges: list[tuple[int, int]],
    ) -> bool:
        """Check if a line index is inside a fenced code block."""
        for start, end in code_ranges:
            if start <= line_idx <= end:
                return True
        return False

    # -------------------------------------------------------------------
    # Scanning methods
    # -------------------------------------------------------------------

    def scan_content(self, content: str, file_path: str = "<string>") -> list[Finding]:
        """Scan a string for security issues.

        Context-aware: patterns found inside Anti-Patterns sections or
        code blocks preceded by warnings are downgraded to INFO severity.

        Args:
            content: Text content to scan.
            file_path: File path for reporting (doesn't need to exist).

        Returns:
            List of Finding objects.
        """
        findings: list[Finding] = []
        lines = content.split("\n")
        code_ranges = self._get_code_block_ranges(lines)

        for line_idx, line in enumerate(lines):
            line_number = line_idx + 1  # 1-indexed

            for compiled, rule_id, message, category, severity in self._all_rules:
                if compiled.search(line):
                    # Context awareness: check if in Anti-Patterns section
                    in_antipattern = self._is_in_antipattern_context(lines, line_idx)
                    in_code = self._is_in_code_block(line_idx, code_ranges)

                    # Downgrade severity if pattern is in an anti-pattern context
                    effective_severity = severity
                    if in_antipattern and in_code:
                        effective_severity = Severity.INFO
                    elif in_antipattern:
                        effective_severity = Severity.LOW

                    suggestion = self._CATEGORY_SUGGESTIONS.get(category, "")
                    if effective_severity == Severity.INFO:
                        suggestion = "In Anti-Patterns context — likely an example of what NOT to do."

                    findings.append(Finding(
                        rule_id=rule_id,
                        category=category,
                        severity=effective_severity,
                        message=message,
                        file_path=file_path,
                        line_number=line_number,
                        line_content=line.strip()[:120],
                        suggestion=suggestion,
                    ))

        return findings

    def scan_file(self, path: str) -> list[Finding]:
        """Scan a single file for security issues.

        Args:
            path: Path to the file to scan.

        Returns:
            List of Finding objects.
        """
        content = Path(path).read_text(encoding="utf-8")
        return self.scan_content(content, file_path=path)

    def scan_directory(
        self, dir_path: str, extensions: tuple[str, ...] = (".md",),
    ) -> ScanResult:
        """Scan all matching files in a directory.

        Args:
            dir_path: Path to directory to scan (recursive).
            extensions: File extensions to include (default: .md only).

        Returns:
            ScanResult with aggregated findings.
        """
        root = Path(dir_path)
        all_findings: list[Finding] = []
        files_scanned = 0

        for ext in extensions:
            pattern = f"*{ext}"
            for file_path in sorted(root.rglob(pattern)):
                if file_path.is_file():
                    all_findings.extend(self.scan_file(str(file_path)))
                    files_scanned += 1

        return ScanResult(
            files_scanned=files_scanned,
            findings=all_findings,
        )

    # -------------------------------------------------------------------
    # Reporting
    # -------------------------------------------------------------------

    def report(self, result: ScanResult, fmt: str = "table") -> str:
        """Generate human-readable report.

        Args:
            result: ScanResult from a scan operation.
            fmt: Output format — "table", "json", or "markdown".

        Returns:
            Formatted report string.
        """
        if fmt == "json":
            return self._report_json(result)
        if fmt == "markdown":
            return self._report_markdown(result)
        return self._report_table(result)

    def _report_table(self, result: ScanResult) -> str:
        """Plain-text table report."""
        lines: list[str] = []
        lines.append("")
        lines.append("=" * 80)
        lines.append("  RepoForge Security Scan Report")
        lines.append("=" * 80)

        if not result.findings:
            lines.append("")
            lines.append("  No security issues found.")
            lines.append(f"  Files scanned: {result.files_scanned}")
            lines.append("")
            lines.append("=" * 80)
            return "\n".join(lines) + "\n"

        # Group findings by severity
        by_severity: dict[Severity, list[Finding]] = {}
        for f in result.findings:
            by_severity.setdefault(f.severity, []).append(f)

        severity_order = [
            Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM,
            Severity.LOW, Severity.INFO,
        ]
        severity_icons = {
            Severity.CRITICAL: "\u274c",
            Severity.HIGH: "\u26a0\ufe0f ",
            Severity.MEDIUM: "\u2139\ufe0f ",
            Severity.LOW: "\u2022",
            Severity.INFO: "\u2022",
        }

        for sev in severity_order:
            findings = by_severity.get(sev, [])
            if not findings:
                continue

            icon = severity_icons[sev]
            lines.append(f"\n  {icon} {sev.value.upper()} ({len(findings)})")
            lines.append("  " + "-" * 60)

            for f in findings:
                lines.append(f"  [{f.rule_id}] {f.message}")
                lines.append(f"    File: {f.file_path}:{f.line_number}")
                lines.append(f"    Line: {f.line_content}")
                if f.suggestion:
                    lines.append(f"    Fix:  {f.suggestion}")

        # Summary
        lines.append(f"\n{'=' * 80}")
        lines.append(
            f"  Files: {result.files_scanned}  |  "
            f"Findings: {len(result.findings)}  |  "
            f"\u274c {result.critical_count} critical  "
            f"\u26a0\ufe0f  {result.high_count} high  "
            f"\u2139\ufe0f  {result.medium_count} medium  "
            f"\u2022 {result.low_count} low  "
            f"\u2022 {result.info_count} info"
        )
        status = "\u2705 PASSED" if result.passed else "\u274c FAILED"
        lines.append(f"  Status: {status}")
        lines.append("=" * 80)

        return "\n".join(lines) + "\n"

    def _report_json(self, result: ScanResult) -> str:
        """JSON report."""
        data = {
            "files_scanned": result.files_scanned,
            "passed": result.passed,
            "summary": {
                "critical": result.critical_count,
                "high": result.high_count,
                "medium": result.medium_count,
                "low": result.low_count,
                "info": result.info_count,
                "total": len(result.findings),
            },
            "findings": [
                {
                    "rule_id": f.rule_id,
                    "category": f.category,
                    "severity": f.severity.value,
                    "message": f.message,
                    "file_path": f.file_path,
                    "line_number": f.line_number,
                    "line_content": f.line_content,
                    "suggestion": f.suggestion,
                }
                for f in result.findings
            ],
        }
        return json.dumps(data, indent=2)

    def _report_markdown(self, result: ScanResult) -> str:
        """Markdown report."""
        lines: list[str] = []
        lines.append("# Security Scan Report\n")

        if not result.findings:
            lines.append("No security issues found.\n")
            lines.append(f"**Files scanned**: {result.files_scanned}\n")
            return "\n".join(lines) + "\n"

        # Summary table
        lines.append("## Summary\n")
        lines.append("| Metric | Count |")
        lines.append("|--------|-------|")
        lines.append(f"| Files scanned | {result.files_scanned} |")
        lines.append(f"| Critical | {result.critical_count} |")
        lines.append(f"| High | {result.high_count} |")
        lines.append(f"| Medium | {result.medium_count} |")
        lines.append(f"| Low | {result.low_count} |")
        lines.append(f"| Info | {result.info_count} |")
        lines.append(f"| **Total** | **{len(result.findings)}** |")
        status = "PASSED" if result.passed else "FAILED"
        lines.append(f"\n**Status**: {status}\n")

        # Findings table
        lines.append("## Findings\n")
        lines.append("| Rule | Severity | Category | Message | File | Line |")
        lines.append("|------|----------|----------|---------|------|------|")

        for f in result.findings:
            lines.append(
                f"| {f.rule_id} | {f.severity.value} | {f.category} "
                f"| {f.message} | {f.file_path} | {f.line_number} |"
            )

        lines.append("")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def scan_generated_output(workspace: str) -> ScanResult:
    """Convenience: scan all generated .md output in a workspace.

    Scans .claude/skills/, .opencode/skills/, and any adapter outputs.

    Args:
        workspace: Path to the project root.

    Returns:
        ScanResult with findings from all scanned directories.
    """
    root = Path(workspace)
    scanner = SecurityScanner()
    all_findings: list[Finding] = []
    files_scanned = 0

    # Directories to scan
    scan_dirs = [
        root / ".claude" / "skills",
        root / ".claude" / "agents",
        root / ".opencode" / "skills",
        root / ".opencode" / "agents",
    ]

    # Also scan adapter outputs at project root
    adapter_files = [
        root / "AGENTS.md",
        root / "GEMINI.md",
        root / ".github" / "copilot-instructions.md",
    ]

    for scan_dir in scan_dirs:
        if scan_dir.exists():
            result = scanner.scan_directory(str(scan_dir))
            all_findings.extend(result.findings)
            files_scanned += result.files_scanned

    for adapter_file in adapter_files:
        if adapter_file.exists():
            all_findings.extend(scanner.scan_file(str(adapter_file)))
            files_scanned += 1

    # Cursor rules
    cursor_dir = root / ".cursor" / "rules"
    if cursor_dir.exists():
        result = scanner.scan_directory(str(cursor_dir), extensions=(".mdc",))
        all_findings.extend(result.findings)
        files_scanned += result.files_scanned

    return ScanResult(
        files_scanned=files_scanned,
        findings=all_findings,
    )
