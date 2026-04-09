"""Pipeline Stage 5: LLM generation + post-processing per chapter."""

import logging

logger = logging.getLogger(__name__)


def generate_chapter(llm, chapter: dict, log) -> str:
    """Call LLM to generate a single chapter. Returns raw content."""
    content = llm.complete(chapter["user"], system=chapter["system"])
    return content.strip() + "\n"


def postprocess_chapter(
    content: str,
    chapter: dict,
    *,
    facts: list,
    build_info,
    ast_symbols: dict | None,
    do_post_process: bool,
    do_verify: bool,
    llm=None,
    verify_model: str | None = None,
    log=None,
) -> tuple[str, list[dict]]:
    """Apply Stage D (deterministic) and Stage C (LLM verification).

    Returns (final_content, corrections_log_entries).
    """
    corrections_log: list[dict] = []

    # Always strip CoT preamble (regardless of post-process/verify settings)
    try:
        from ..intelligence.post_process import Correction, _strip_cot_preamble
        cot_corrections: list[Correction] = []
        content = _strip_cot_preamble(content, cot_corrections)
        if cot_corrections:
            if log:
                log(f" 🧹CoT:{len(cot_corrections)}", end="")
            corrections_log.append({
                "file": chapter["file"],
                "stage": "CoT",
                "corrections": [
                    {"original": c.original, "corrected": c.corrected,
                     "reason": c.reason, "line": c.line}
                    for c in cot_corrections
                ],
            })
    except Exception:
        pass  # CoT stripping is best-effort

    # Stage D: Deterministic post-processing
    if do_post_process:
        try:
            from ..intelligence.post_process import post_process_chapter as _pp
            content, d_corrections = _pp(
                content=content,
                facts=facts,
                build_info=build_info,
                ast_symbols=ast_symbols,
                chapter_file=chapter["file"],
            )
            if d_corrections:
                if log:
                    log(f" 🔧D:{len(d_corrections)}", end="")
                corrections_log.append({
                    "file": chapter["file"],
                    "stage": "D",
                    "corrections": [
                        {"original": c.original, "corrected": c.corrected,
                         "reason": c.reason, "line": c.line}
                        for c in d_corrections
                    ],
                })
        except (ImportError, ValueError, KeyError) as e:
            # ImportError: post-processor missing; ValueError/KeyError: correction parse errors
            if log:
                log(f" ⚠️D:{e}", end="")

    # Stage C: LLM verification
    if do_verify and llm is not None:
        try:
            from ..intelligence.verifier import verify_chapter as _vc
            content, v_issues = _vc(
                chapter_content=content,
                facts=facts,
                ast_symbols=ast_symbols,
                llm=llm,
                model=verify_model,
            )
            if v_issues:
                if log:
                    log(f" 🔍C:{len(v_issues)}", end="")
                corrections_log.append({
                    "file": chapter["file"],
                    "stage": "C",
                    "issues": v_issues,
                })
        except (ImportError, ValueError, RuntimeError) as e:
            # ImportError: verifier missing; ValueError: parse error; RuntimeError: LLM call failure
            if log:
                log(f" ⚠️C:{e}", end="")

    return content, corrections_log
