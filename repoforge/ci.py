"""CI integration — git-aware diff, doc drift detection, quality gate.

Designed for local CI pipelines (Docker + GHAGGA) and pre-push hooks.
No GitHub Actions dependency.

Usage:
    from repoforge.ci import detect_changed_files, detect_doc_drift, quality_gate

    # What changed since last commit?
    changed = detect_changed_files(repo_root)

    # Are docs stale relative to source?
    drift = detect_doc_drift(repo_root, docs_dir="docs")

    # CI gate: fail if doc quality below threshold
    result = quality_gate("docs/", threshold=0.7)
    sys.exit(result.exit_code)
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .cache import hash_content, compute_repo_snapshot
from .scoring import DocScorer, DocScore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Git-aware change detection
# ---------------------------------------------------------------------------


def detect_changed_files(repo_root: Path) -> list[str]:
    """Detect files changed since last commit (staged + unstaged + untracked).

    Returns relative paths. Works with any git repo.
    """
    repo_root = Path(repo_root)
    changed: list[str] = []

    try:
        # Modified + staged
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=repo_root, capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            changed.extend(
                l.strip() for l in result.stdout.strip().splitlines() if l.strip()
            )

        # Untracked files
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=repo_root, capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            changed.extend(
                l.strip() for l in result.stdout.strip().splitlines() if l.strip()
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git not available, cannot detect changed files")

    return sorted(set(changed))


# ---------------------------------------------------------------------------
# Doc drift detection
# ---------------------------------------------------------------------------


@dataclass
class DriftReport:
    """Report on whether generated docs are stale relative to source."""

    is_stale: bool = False
    source_hash: str = ""
    docs_hash: str = ""
    changed_sources: list[str] = field(default_factory=list)


def detect_doc_drift(
    repo_root: Path,
    docs_dir: Path | None = None,
) -> DriftReport:
    """Compare source code state against generated docs state.

    Computes a combined hash of all source files and all doc files.
    If the source hash changes but docs hash doesn't, docs are stale.
    """
    repo_root = Path(repo_root)
    docs_dir = Path(docs_dir) if docs_dir else repo_root / "docs"

    # Hash source files
    source_snap = compute_repo_snapshot(repo_root)
    source_hash = hash_content(str(sorted(source_snap["files"].items())))

    # Hash doc files
    docs_hash = ""
    if docs_dir.exists():
        doc_files = {}
        for md in sorted(docs_dir.glob("*.md")):
            try:
                doc_files[md.name] = hash_content(md.read_text(encoding="utf-8"))
            except Exception:
                pass
        docs_hash = hash_content(str(sorted(doc_files.items())))

    return DriftReport(
        source_hash=source_hash,
        docs_hash=docs_hash,
    )


# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------


@dataclass
class GateResult:
    """Result of a documentation quality gate check."""

    passed: bool
    threshold: float
    min_score: float = 0.0
    scores: list[DocScore] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return 0 if self.passed else 1


def quality_gate(docs_dir: str, threshold: float = 0.7) -> GateResult:
    """Run quality gate on generated docs. Returns pass/fail with details.

    Usage in CI:
        result = quality_gate("docs/", threshold=0.7)
        sys.exit(result.exit_code)
    """
    scorer = DocScorer()
    scores = scorer.score_directory(docs_dir)

    if not scores:
        return GateResult(passed=True, threshold=threshold, scores=[])

    min_score = min(s.overall for s in scores)

    return GateResult(
        passed=min_score >= threshold,
        threshold=threshold,
        min_score=round(min_score, 3),
        scores=scores,
    )
