"""
scorer.py - Deterministic quality scoring for SKILL.md files.

Scores skills across 7 dimensions (no LLM needed):
  1. Completeness (20%) — Required sections present?
  2. Clarity (15%)      — Concise, actionable language?
  3. Specificity (20%)  — References real repo artifacts?
  4. Examples (15%)     — Concrete code examples?
  5. Format (10%)       — Valid YAML frontmatter, markdown structure?
  6. Safety (10%)       — No destructive commands without warnings?
  7. Agent Readiness (10%) — Usable by an AI agent?

Works standalone: can score any SKILL.md, not just RepoForge-generated ones.
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

DIMENSION_WEIGHTS = {
    "completeness": 0.20,
    "clarity": 0.15,
    "specificity": 0.20,
    "examples": 0.15,
    "format": 0.10,
    "safety": 0.10,
    "agent_readiness": 0.10,
}


@dataclass
class SkillScore:
    """Quality score for a single SKILL.md file."""
    file_path: str
    completeness: float = 0.0
    clarity: float = 0.0
    specificity: float = 0.0
    examples: float = 0.0
    format_score: float = 0.0
    safety: float = 0.0
    agent_readiness: float = 0.0
    overall: float = 0.0
    details: dict = field(default_factory=dict)

    @property
    def grade(self) -> str:
        if self.overall >= 0.85:
            return "PASS"
        if self.overall >= 0.60:
            return "WARN"
        return "FAIL"

    @property
    def grade_emoji(self) -> str:
        if self.overall >= 0.85:
            return "\u2705"
        if self.overall >= 0.60:
            return "\u26a0\ufe0f "
        return "\u274c"


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class SkillScorer:
    """Deterministic SKILL.md quality scorer."""

    def __init__(self, repo_map: dict | None = None):
        """Initialize with optional repo_map for specificity checking.

        Args:
            repo_map: Output from scan_repo(). When provided, specificity
                      checks validate that referenced file paths actually
                      exist in the repo.
        """
        self.repo_map = repo_map
        self._repo_paths: set[str] = set()
        if repo_map:
            for layer in repo_map.get("layers", {}).values():
                for mod in layer.get("modules", []):
                    self._repo_paths.add(mod.get("path", ""))

    def score_file(self, path: str) -> SkillScore:
        """Score a single SKILL.md file."""
        content = Path(path).read_text(encoding="utf-8")
        return self._score_content(content, path)

    def score_directory(self, skills_dir: str) -> list[SkillScore]:
        """Score all SKILL.md files in a directory (recursive)."""
        root = Path(skills_dir)
        scores = []
        for skill_path in sorted(root.rglob("SKILL.md")):
            scores.append(self.score_file(str(skill_path)))
        return scores

    def _score_content(self, content: str, file_path: str) -> SkillScore:
        """Score raw SKILL.md content string."""
        score = SkillScore(file_path=file_path)

        score.completeness, score.details["completeness"] = self._score_completeness(content)
        score.clarity, score.details["clarity"] = self._score_clarity(content)
        score.specificity, score.details["specificity"] = self._score_specificity(content)
        score.examples, score.details["examples"] = self._score_examples(content)
        score.format_score, score.details["format"] = self._score_format(content)
        score.safety, score.details["safety"] = self._score_safety(content)
        score.agent_readiness, score.details["agent_readiness"] = self._score_agent_readiness(
            content
        )

        # Weighted overall
        score.overall = (
            score.completeness * DIMENSION_WEIGHTS["completeness"]
            + score.clarity * DIMENSION_WEIGHTS["clarity"]
            + score.specificity * DIMENSION_WEIGHTS["specificity"]
            + score.examples * DIMENSION_WEIGHTS["examples"]
            + score.format_score * DIMENSION_WEIGHTS["format"]
            + score.safety * DIMENSION_WEIGHTS["safety"]
            + score.agent_readiness * DIMENSION_WEIGHTS["agent_readiness"]
        )

        return score

    # -----------------------------------------------------------------------
    # Dimension scorers — each returns (score: float, detail: dict)
    # -----------------------------------------------------------------------

    def _score_completeness(self, content: str) -> tuple[float, dict]:
        """Check for presence of required sections."""
        checks = {
            "description": bool(
                re.search(r"^description:", content, re.MULTILINE)
                or re.search(r"##\s*(What|Description|Overview)", content, re.IGNORECASE)
            ),
            "trigger": bool(
                re.search(r"Trigger:", content, re.IGNORECASE)
            ),
            "commands": bool(
                re.search(r"##\s*(Commands|Quick Reference)", content, re.IGNORECASE)
            ),
            "patterns": bool(
                re.search(r"##\s*(Critical Patterns|Patterns|Key Patterns)", content, re.IGNORECASE)
            ),
            "anti_patterns": bool(
                re.search(r"##\s*(Anti-?Patterns?|Pitfalls|Don'?t)", content, re.IGNORECASE)
            ),
            "when_to_use": bool(
                re.search(r"##\s*(When to Use|When to use|Usage)", content, re.IGNORECASE)
            ),
        }

        found = sum(1 for v in checks.values() if v)
        total = len(checks)
        score = found / total if total > 0 else 0.0

        return score, {
            "found": found,
            "total": total,
            "sections": checks,
        }

    def _score_clarity(self, content: str) -> tuple[float, dict]:
        """Heuristics for clear, concise language."""
        lines = content.split("\n")
        total_lines = len(lines)
        if total_lines == 0:
            return 0.0, {"reason": "empty file"}

        penalties = 0.0
        bonuses = 0.0
        issues: list[str] = []

        # Penalize lines > 120 chars (verbose)
        long_lines = sum(1 for line in lines if len(line) > 120)
        if long_lines > 0:
            ratio = long_lines / total_lines
            pen = min(ratio * 2.0, 0.3)
            penalties += pen
            issues.append(f"{long_lines} lines >120 chars")

        # Penalize wall-of-text paragraphs (>5 consecutive non-empty, non-code, non-bullet lines)
        wall_count = 0
        consecutive = 0
        in_code_block = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                consecutive = 0
                continue
            if in_code_block:
                consecutive = 0
                continue
            is_prose = (
                stripped
                and not stripped.startswith(("-", "*", "|", "#", ">", "```"))
                and not re.match(r"^\d+\.", stripped)
            )
            if is_prose:
                consecutive += 1
                if consecutive > 5:
                    wall_count += 1
            else:
                consecutive = 0

        if wall_count > 0:
            penalties += min(wall_count * 0.1, 0.3)
            issues.append(f"{wall_count} wall-of-text paragraphs")

        # Reward bullet points and tables
        bullet_lines = sum(1 for line in lines if line.strip().startswith(("-", "*")))
        table_lines = sum(1 for line in lines if "|" in line and line.strip().startswith("|"))
        structure_ratio = (bullet_lines + table_lines) / total_lines if total_lines > 0 else 0
        if structure_ratio > 0.1:
            bonuses += 0.15
        if structure_ratio > 0.2:
            bonuses += 0.1

        # Penalize filler words
        filler_words = ["simply", "just", "basically", "obviously", "very", "really", "actually"]
        content_lower = content.lower()
        filler_count = sum(
            len(re.findall(r"\b" + w + r"\b", content_lower))
            for w in filler_words
        )
        if filler_count > 3:
            penalties += min(filler_count * 0.03, 0.2)
            issues.append(f"{filler_count} filler words")

        score = max(0.0, min(1.0, 1.0 - penalties + bonuses))
        return score, {"penalties": penalties, "bonuses": bonuses, "issues": issues}

    def _score_specificity(self, content: str) -> tuple[float, dict]:
        """Check if content references real repo artifacts."""
        # Generic phrases to penalize
        generic_phrases = [
            r"your project",
            r"your application",
            r"your app",
            r"as needed",
            r"your module",
            r"your service",
            r"your component",
        ]

        content_lower = content.lower()
        generic_count = sum(
            len(re.findall(phrase, content_lower))
            for phrase in generic_phrases
        )

        # Count specific file path references (anything that looks like a/b/c.ext)
        path_refs = re.findall(r"`[a-zA-Z0-9_./-]+\.[a-zA-Z]{1,5}`", content)
        specific_count = len(path_refs)

        # Count module/function name references (backtick-wrapped identifiers)
        ident_refs = re.findall(r"`[a-zA-Z_][a-zA-Z0-9_]+`", content)
        specific_count += len(ident_refs)

        # If repo_map provided, check that mentioned paths exist
        verified_paths = 0
        if self._repo_paths and path_refs:
            for ref in path_refs:
                clean = ref.strip("`")
                if clean in self._repo_paths:
                    verified_paths += 1

        # Score based on ratio of specific vs generic signals
        total_signals = specific_count + generic_count
        if total_signals == 0:
            score = 0.3  # no signals either way — mediocre
        else:
            score = specific_count / total_signals

        # Bonus for verified paths
        if verified_paths > 0:
            score = min(1.0, score + 0.1)

        # Penalty for high generic count
        if generic_count > 5:
            score = max(0.0, score - 0.15)

        return score, {
            "specific_refs": specific_count,
            "generic_phrases": generic_count,
            "verified_paths": verified_paths,
        }

    def _score_examples(self, content: str) -> tuple[float, dict]:
        """Check for code blocks quality and quantity."""
        # Find all fenced code blocks
        code_blocks = re.findall(r"```(\w*)\n(.*?)```", content, re.DOTALL)
        num_blocks = len(code_blocks)

        if num_blocks == 0:
            return 0.0, {"blocks": 0, "with_lang": 0, "with_code": 0, "issues": ["no code blocks"]}

        # Check language tags
        with_lang = sum(1 for lang, _ in code_blocks if lang.strip())

        # Check blocks have actual code (not just comments or empty)
        with_code = 0
        for _, body in code_blocks:
            # Strip comments and whitespace
            code_lines = [
                line for line in body.strip().split("\n")
                if line.strip()
                and not line.strip().startswith(("#", "//", "/*", "*", "<!--"))
            ]
            if code_lines:
                with_code += 1

        # Scoring
        score = 0.0

        # Base: having code blocks at all
        if num_blocks >= 1:
            score += 0.3
        if num_blocks >= 2:
            score += 0.2
        if num_blocks >= 3:
            score += 0.1

        # Language tags
        lang_ratio = with_lang / num_blocks if num_blocks > 0 else 0
        score += lang_ratio * 0.2

        # Actual code content
        code_ratio = with_code / num_blocks if num_blocks > 0 else 0
        score += code_ratio * 0.2

        score = min(1.0, score)

        return score, {
            "blocks": num_blocks,
            "with_lang": with_lang,
            "with_code": with_code,
        }

    def _score_format(self, content: str) -> tuple[float, dict]:
        """Validate markdown structure."""
        checks: dict[str, bool] = {}
        issues: list[str] = []

        # YAML frontmatter present and valid
        has_frontmatter = content.strip().startswith("---")
        if has_frontmatter:
            fm_match = re.match(r"---\s*\n(.*?)\n---", content, re.DOTALL)
            if fm_match:
                checks["frontmatter_valid"] = True
                fm_body = fm_match.group(1)
                # Required frontmatter fields
                checks["fm_has_name"] = bool(re.search(r"^name:", fm_body, re.MULTILINE))
                checks["fm_has_description"] = bool(
                    re.search(r"^description:", fm_body, re.MULTILINE)
                )
                if not checks["fm_has_name"]:
                    issues.append("missing name in frontmatter")
                if not checks["fm_has_description"]:
                    issues.append("missing description in frontmatter")
            else:
                checks["frontmatter_valid"] = False
                issues.append("frontmatter not properly closed")
        else:
            checks["frontmatter_valid"] = False
            checks["fm_has_name"] = False
            checks["fm_has_description"] = False
            issues.append("no YAML frontmatter")

        # Header hierarchy: no h3 (###) before first h2 (##)
        headers = re.findall(r"^(#{1,6})\s", content, re.MULTILINE)
        first_h2_found = False
        bad_hierarchy = False
        for h in headers:
            level = len(h)
            if level == 2:
                first_h2_found = True
            elif level >= 3 and not first_h2_found:
                bad_hierarchy = True
                break
        checks["header_hierarchy"] = not bad_hierarchy
        if bad_hierarchy:
            issues.append("h3 before any h2")

        # No unclosed code blocks
        backtick_count = len(re.findall(r"^```", content, re.MULTILINE))
        checks["code_blocks_closed"] = backtick_count % 2 == 0
        if backtick_count % 2 != 0:
            issues.append("unclosed code block")

        # Score
        passed = sum(1 for v in checks.values() if v)
        total = len(checks)
        score = passed / total if total > 0 else 0.0

        return score, {"checks": checks, "issues": issues}

    def _score_safety(self, content: str) -> tuple[float, dict]:
        """Scan for dangerous patterns."""
        violations: list[str] = []

        # Destructive commands without warnings
        dangerous_cmds = [
            (r"rm\s+-rf\s+/", "rm -rf / (root deletion)"),
            (r"rm\s+-rf\s+\*", "rm -rf * (wildcard deletion)"),
            (r"DROP\s+TABLE", "DROP TABLE"),
            (r"DROP\s+DATABASE", "DROP DATABASE"),
            (r"git\s+push\s+--force\s+.*main", "force push to main"),
            (r"git\s+push\s+--force\s+.*master", "force push to master"),
            (r"git\s+reset\s+--hard", "git reset --hard"),
        ]
        for pattern, name in dangerous_cmds:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                # Check if there's a warning nearby (within 3 lines)
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    start = max(0, match.start() - 200)
                    context = content[start:match.end() + 200].lower()
                    has_warning = any(
                        w in context
                        for w in ["warning", "caution", "danger", "careful", "⚠", "don't", "bad"]
                    )
                    if not has_warning:
                        violations.append(f"unwarned: {name}")

        # Hardcoded secrets patterns
        secret_patterns = [
            (r"['\"]sk-[a-zA-Z0-9]{20,}['\"]", "OpenAI API key"),
            (r"['\"]ghp_[a-zA-Z0-9]{20,}['\"]", "GitHub token"),
            (r"['\"]AKIA[A-Z0-9]{12,}['\"]", "AWS access key"),
            (r"password\s*=\s*['\"][^'\"]{8,}['\"]", "hardcoded password"),
        ]
        for pattern, name in secret_patterns:
            if re.search(pattern, content):
                violations.append(f"secret: {name}")

        # Prompt injection patterns
        injection_patterns = [
            (r"ignore\s+(all\s+)?previous\s+instructions?", "prompt injection"),
            (r"you\s+are\s+now\s+a", "role override"),
            (r"^system:", "system message injection"),
        ]
        for pattern, name in injection_patterns:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                violations.append(f"injection: {name}")

        # Dangerous code patterns without context
        risky_code = [
            (r"\beval\s*\(", "eval()"),
            (r"\bexec\s*\(", "exec()"),
            (r"os\.system\s*\(", "os.system()"),
        ]
        for pattern, name in risky_code:
            matches = list(re.finditer(pattern, content))
            if matches:
                for match in matches:
                    start = max(0, match.start() - 200)
                    context = content[start:match.end() + 200].lower()
                    has_warning = any(
                        w in context
                        for w in ["warning", "caution", "danger", "avoid", "don't", "bad", "anti"]
                    )
                    if not has_warning:
                        violations.append(f"risky: {name}")

        # Penalty: 0.15 per violation, max to 1.0 total
        penalty = min(len(violations) * 0.15, 1.0)
        score = max(0.0, 1.0 - penalty)

        return score, {"violations": violations, "violation_count": len(violations)}

    def _score_agent_readiness(self, content: str) -> tuple[float, dict]:
        """Check if an AI agent could use this skill effectively."""
        checks: dict[str, bool] = {}

        # Has clear trigger description
        checks["has_trigger"] = bool(
            re.search(r"Trigger:", content, re.IGNORECASE)
        )

        # Commands are executable (code blocks in Commands section or bash blocks)
        commands_section = re.search(
            r"##\s*Commands(.*?)(?=##|\Z)", content, re.DOTALL | re.IGNORECASE
        )
        if commands_section:
            has_bash = bool(re.search(r"```(?:bash|sh|shell)", commands_section.group(1)))
            checks["executable_commands"] = has_bash
        else:
            checks["executable_commands"] = False

        # File paths are specific (backtick-wrapped paths with extensions)
        path_refs = re.findall(r"`[a-zA-Z0-9_./-]+\.[a-zA-Z]{1,5}`", content)
        checks["specific_paths"] = len(path_refs) >= 2

        # Has Quick Reference table
        checks["quick_reference"] = bool(
            re.search(r"##\s*Quick Reference", content, re.IGNORECASE)
            and re.search(r"\|.*\|.*\|", content)
        )

        # Has structured "When to Use" section
        checks["when_to_use"] = bool(
            re.search(r"##\s*When to Use", content, re.IGNORECASE)
        )

        passed = sum(1 for v in checks.values() if v)
        total = len(checks)
        score = passed / total if total > 0 else 0.0

        return score, {"checks": checks}

    # -----------------------------------------------------------------------
    # Reporting
    # -----------------------------------------------------------------------

    def report(self, scores: list[SkillScore], fmt: str = "table") -> str:
        """Generate a human-readable report.

        Args:
            scores: List of SkillScore objects.
            fmt: "table", "json", or "markdown".
        """
        if fmt == "json":
            return self._report_json(scores)
        if fmt == "markdown":
            return self._report_markdown(scores)
        return self._report_table(scores)

    def _report_table(self, scores: list[SkillScore]) -> str:
        """Plain-text table report."""
        if not scores:
            return "No SKILL.md files found.\n"

        lines: list[str] = []
        lines.append("")
        lines.append("=" * 80)
        lines.append("  RepoForge Skill Quality Report")
        lines.append("=" * 80)

        dims = [
            ("Completeness", "completeness", DIMENSION_WEIGHTS["completeness"]),
            ("Clarity", "clarity", DIMENSION_WEIGHTS["clarity"]),
            ("Specificity", "specificity", DIMENSION_WEIGHTS["specificity"]),
            ("Examples", "examples", DIMENSION_WEIGHTS["examples"]),
            ("Format", "format_score", DIMENSION_WEIGHTS["format"]),
            ("Safety", "safety", DIMENSION_WEIGHTS["safety"]),
            ("Agent Ready", "agent_readiness", DIMENSION_WEIGHTS["agent_readiness"]),
        ]

        for s in scores:
            name = Path(s.file_path).parent.name
            if name == ".":
                name = Path(s.file_path).stem
            lines.append(f"\n{s.grade_emoji} {name}  ({s.overall:.0%} — {s.grade})")
            lines.append(f"   File: {s.file_path}")

            for label, attr, weight in dims:
                val = getattr(s, attr)
                bar = "\u2588" * int(val * 10) + "\u2591" * (10 - int(val * 10))
                weight_pct = f"{weight:.0%}"
                lines.append(f"   {label:<14} [{bar}] {val:.0%}  (w={weight_pct})")

        # Summary
        if scores:
            avg = sum(s.overall for s in scores) / len(scores)
            passing = sum(1 for s in scores if s.overall >= 0.85)
            warning = sum(1 for s in scores if 0.60 <= s.overall < 0.85)
            failing = sum(1 for s in scores if s.overall < 0.60)

            lines.append(f"\n{'=' * 80}")
            lines.append(f"  Average: {avg:.0%}  |  "
                         f"\u2705 {passing} passed  "
                         f"\u26a0\ufe0f  {warning} warnings  "
                         f"\u274c {failing} failed")
            lines.append("=" * 80)

        return "\n".join(lines) + "\n"

    def _report_json(self, scores: list[SkillScore]) -> str:
        """JSON report."""
        data = []
        for s in scores:
            data.append({
                "file_path": s.file_path,
                "overall": round(s.overall, 3),
                "grade": s.grade,
                "dimensions": {
                    "completeness": round(s.completeness, 3),
                    "clarity": round(s.clarity, 3),
                    "specificity": round(s.specificity, 3),
                    "examples": round(s.examples, 3),
                    "format": round(s.format_score, 3),
                    "safety": round(s.safety, 3),
                    "agent_readiness": round(s.agent_readiness, 3),
                },
                "details": s.details,
            })
        return json.dumps(data, indent=2)

    def _report_markdown(self, scores: list[SkillScore]) -> str:
        """Markdown report."""
        if not scores:
            return "No SKILL.md files found.\n"

        lines: list[str] = []
        lines.append("# Skill Quality Report\n")

        # Summary table
        lines.append("| Skill | Overall | Compl. | Clarity | Specif. | Examples "
                      "| Format | Safety | Agent | Grade |")
        lines.append("|-------|---------|--------|---------|---------|---------- "
                      "|--------|--------|-------|-------|")

        for s in scores:
            name = Path(s.file_path).parent.name
            if name == ".":
                name = Path(s.file_path).stem
            lines.append(
                f"| {name} | {s.overall:.0%} | {s.completeness:.0%} | {s.clarity:.0%} "
                f"| {s.specificity:.0%} | {s.examples:.0%} | {s.format_score:.0%} "
                f"| {s.safety:.0%} | {s.agent_readiness:.0%} | {s.grade_emoji} {s.grade} |"
            )

        # Average
        if scores:
            avg = sum(s.overall for s in scores) / len(scores)
            lines.append(f"\n**Average score: {avg:.0%}**\n")

        return "\n".join(lines) + "\n"
