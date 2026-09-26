"""The skill draft gate rejects literals and calls the source does not contain."""

from repoforge.skill_bindings import (
    declarations_block,
    settle_skill_draft,
    skill_draft_problems,
)

TYPES = """
export type GenerationMode = 'docs' | 'skills' | 'both';

export interface GenerateRequest {
  mode: GenerationMode;
}
"""

HARNESS = """
def make_fastapi_crud_module():
    return {}, {}

def select_code_snippets(graph, root_dir, token_budget=2000):
    return []
"""


def _skill(body: str) -> str:
    return f"---\nname: sample\n---\n\n{body}\n"


class _Scripted:
    def __init__(self, replies: list[str]):
        self.replies = list(replies)

    def complete(self, prompt: str, system: str | None = None) -> str:
        return self.replies.pop(0)


def test_declarations_include_the_union_literal():
    block = declarations_block([("apps/web/src/lib/types.ts", TYPES)])

    assert "export type GenerationMode = 'docs' | 'skills' | 'both'" in block
    assert "EXACT declarations" in block


def test_chat_mode_is_rejected_and_docs_is_accepted():
    sources = [("apps/web/src/lib/types.ts", TYPES)]

    rejected = skill_draft_problems(
        _skill("const req = { mode: \"chat\" as GenerationMode };"),
        sources,
    )
    accepted = skill_draft_problems(
        _skill("const req = { mode: 'docs' };"),
        sources,
    )

    assert any("chat" in problem and "GenerationMode" in problem for problem in rejected)
    assert accepted == []


def test_factory_call_with_arguments_is_rejected():
    sources = [("eval/harness.py", HARNESS)]

    rejected = skill_draft_problems(
        _skill('mod = make_fastapi_crud_module(name="reports")'),
        sources,
    )
    accepted = skill_draft_problems(
        _skill("mod = make_fastapi_crud_module()"),
        sources,
    )
    wrong_keyword = skill_draft_problems(
        _skill("select_code_snippets(files, max_tokens=1500)"),
        sources,
    )

    assert any("name" in problem for problem in rejected)
    assert accepted == []
    assert any("max_tokens" in problem for problem in wrong_keyword)


def test_empty_fence_and_transcript_are_rejected():
    assert skill_draft_problems("  ", []) == ["draft is empty"]
    assert skill_draft_problems("```yaml\n---\nname: x\n---\n```", []) == [
        "draft is wrapped in a fence"
    ]
    assert "tool transcript" in skill_draft_problems('{"type":"step_start"}', [])[0]


def test_one_repair_keeps_a_fixed_draft_and_drops_a_second_failure():
    sources = [("apps/web/src/lib/types.ts", TYPES)]
    bad = _skill('mode: "chat"')
    good = _skill("mode: 'skills'")

    kept, problems = settle_skill_draft(
        _Scripted([good]),
        bad,
        sources,
        system="system",
    )
    dropped, still = settle_skill_draft(
        _Scripted([bad]),
        bad,
        sources,
        system="system",
    )

    assert kept == good
    assert problems == []
    assert dropped is None
    assert still
