"""Refinement loop — generate → score → critique → regenerate.

Uses DocScorer (rule-based, no LLM cost) as the quality gate.
If a chapter scores below threshold, the loop sends the content
back to the LLM with specific feedback about what to improve.

Usage:
    from repoforge.refinement import refine_chapter
    result = refine_chapter(llm, chapter, threshold=0.7, max_iterations=3)
    print(result.final_content, result.iterations, result.converged)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .scoring import DocScorer, DocScore

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLD = 0.65
_DEFAULT_MAX_ITERATIONS = 3


@dataclass
class RefinementResult:
    """Result of the refinement loop."""

    final_content: str
    iterations: int
    score_progression: list[float] = field(default_factory=list)
    converged: bool = False


def refine_chapter(
    llm,
    chapter: dict,
    *,
    threshold: float = _DEFAULT_THRESHOLD,
    max_iterations: int = _DEFAULT_MAX_ITERATIONS,
) -> RefinementResult:
    """Generate a chapter with iterative refinement.

    1. Generate initial content via LLM
    2. Score with DocScorer (rule-based, free)
    3. If score >= threshold → done
    4. Otherwise, build critique prompt and ask LLM to improve
    5. Repeat up to max_iterations
    """
    scorer = DocScorer()
    scores: list[float] = []
    content = ""

    for i in range(max_iterations):
        if i == 0:
            # First iteration: normal generation
            content = llm.complete(chapter["user"], system=chapter["system"])
            content = content.strip() + "\n"
        else:
            # Refinement: send content back with critique
            critique_prompt = _build_critique_prompt(chapter, content, last_score)
            content = llm.complete(critique_prompt, system=chapter["system"])
            content = content.strip() + "\n"

        last_score = scorer.score_content(content, chapter["file"])
        scores.append(last_score.overall)

        logger.info(
            "Refinement iteration %d/%d for %s: score=%.2f (threshold=%.2f)",
            i + 1, max_iterations, chapter["file"], last_score.overall, threshold,
        )

        if last_score.overall >= threshold:
            return RefinementResult(
                final_content=content,
                iterations=i + 1,
                score_progression=scores,
                converged=True,
            )

    return RefinementResult(
        final_content=content,
        iterations=max_iterations,
        score_progression=scores,
        converged=False,
    )


def _build_critique_prompt(chapter: dict, content: str, score: DocScore) -> str:
    """Build a refinement prompt that tells the LLM what to improve."""
    weaknesses = []

    if score.structure < 0.6:
        weaknesses.append(
            "- **Structure**: Add more section headings (## and ###). "
            "Organize content into clear, named sections."
        )
    if score.completeness < 0.6:
        weaknesses.append(
            "- **Completeness**: Add tables for structured data, "
            "Mermaid diagrams for flows, and bullet lists for key points."
        )
    if score.code_quality < 0.4:
        weaknesses.append(
            "- **Code examples**: Add code blocks with language annotations "
            "(```python, ```go, etc.) showing real usage examples."
        )
    if score.clarity < 0.6:
        weaknesses.append(
            "- **Clarity**: Use shorter sentences. Break long paragraphs. "
            "Add more whitespace between sections."
        )

    if not weaknesses:
        weaknesses.append("- Improve overall quality, depth, and specificity.")

    feedback = "\n".join(weaknesses)

    return f"""The following documentation chapter for **{chapter['title']}** scored {score.overall:.2f}/1.00 and needs improvement.

## Areas to improve:
{feedback}

## Current content (rewrite and improve this):

{content}

## Instructions:
Rewrite the chapter above, addressing ALL the improvement areas listed. Keep the same topic and facts but make it significantly better. Output ONLY the improved Markdown — no explanations.
"""
