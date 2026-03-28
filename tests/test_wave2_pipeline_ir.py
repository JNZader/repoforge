"""Tests for Wave 2: Pipeline architecture + IR types."""

from dataclasses import fields

import pytest

from repoforge.ir import ChapterSpec, GeneratedChapter, DocumentationResult


# ── IR dataclasses ───────────────────────────────────────────────────────


class TestChapterSpec:

    def test_required_fields(self):
        spec = ChapterSpec(
            file="01-overview.md",
            title="Overview",
            description="Tech stack and structure",
            project_type="web_service",
            system_prompt="You are a writer.",
            user_prompt="Generate overview.",
        )
        assert spec.file == "01-overview.md"
        assert spec.title == "Overview"
        assert spec.subdir is None

    def test_optional_subdir(self):
        spec = ChapterSpec(
            file="01-overview.md", title="Overview", description="",
            project_type="monorepo", system_prompt="", user_prompt="",
            subdir="backend",
        )
        assert spec.subdir == "backend"

    def test_is_dataclass(self):
        field_names = {f.name for f in fields(ChapterSpec)}
        assert "file" in field_names
        assert "system_prompt" in field_names
        assert "subdir" in field_names


class TestGeneratedChapter:

    def test_defaults(self):
        spec = ChapterSpec("f.md", "T", "D", "generic", "sys", "usr")
        gen = GeneratedChapter(spec=spec, raw_content="raw", final_content="final")
        assert gen.corrections == []
        assert gen.verification_issues == []

    def test_with_corrections(self):
        spec = ChapterSpec("f.md", "T", "D", "generic", "sys", "usr")
        gen = GeneratedChapter(
            spec=spec, raw_content="raw", final_content="fixed",
            corrections=[{"reason": "port fix"}],
        )
        assert len(gen.corrections) == 1


class TestDocumentationResult:

    def test_defaults(self):
        result = DocumentationResult(
            project_name="TestProject", language="English", output_dir="/tmp/docs",
        )
        assert result.chapters == []
        assert result.docsify_files == []
        assert result.errors == []


# ── prompts package backward compat ──────────────────────────────────────


class TestPromptsBackwardCompat:
    """Verify that docs_prompts imports still work after the split."""

    def test_get_chapter_prompts_importable(self):
        from repoforge.docs_prompts import get_chapter_prompts
        assert callable(get_chapter_prompts)

    def test_base_system_importable(self):
        from repoforge.docs_prompts import _base_system
        result = _base_system("English")
        assert "English" in result or "documentation" in result.lower()

    def test_classify_project_importable(self):
        from repoforge.docs_prompts import classify_project
        assert callable(classify_project)


# ── pipeline package ─────────────────────────────────────────────────────


class TestPipelineImports:
    """Verify pipeline modules are importable and have expected functions."""

    def test_context_importable(self):
        from repoforge.pipeline.context import build_all_contexts
        assert callable(build_all_contexts)

    def test_generate_importable(self):
        from repoforge.pipeline.generate import generate_chapter, postprocess_chapter
        assert callable(generate_chapter)
        assert callable(postprocess_chapter)

    def test_write_importable(self):
        from repoforge.pipeline.write import write_chapter, write_docsify, write_corrections_log
        assert callable(write_chapter)
        assert callable(write_docsify)
        assert callable(write_corrections_log)


class TestWriteChapter:
    """Test the write_chapter function."""

    def test_writes_to_correct_path(self, tmp_path):
        from repoforge.pipeline.write import write_chapter

        chapter = {"file": "01-overview.md"}
        result = write_chapter("# Overview\n", chapter, tmp_path)
        assert (tmp_path / "01-overview.md").exists()
        assert (tmp_path / "01-overview.md").read_text() == "# Overview\n"
        assert result == str(tmp_path / "01-overview.md")

    def test_writes_to_subdir_for_monorepo(self, tmp_path):
        from repoforge.pipeline.write import write_chapter

        chapter = {"file": "01-overview.md", "subdir": "backend"}
        result = write_chapter("# Backend\n", chapter, tmp_path)
        assert (tmp_path / "backend" / "01-overview.md").exists()


class TestGenerateChapter:
    """Test generate_chapter with a mock LLM."""

    def test_calls_llm_and_returns_content(self):
        from repoforge.pipeline.generate import generate_chapter

        class FakeLLM:
            def complete(self, prompt, system=None):
                return "  # Generated Content  "

        chapter = {"user": "Generate docs", "system": "You are a writer"}
        result = generate_chapter(FakeLLM(), chapter, lambda *a, **k: None)
        assert result == "# Generated Content\n"


# ── docs_generator backward compat ───────────────────────────────────────


class TestDocsGeneratorBackwardCompat:
    """Verify that docs_generator exports still work after pipeline extraction."""

    def test_generate_docs_importable(self):
        from repoforge.docs_generator import generate_docs
        assert callable(generate_docs)

    def test_infer_project_name_importable(self):
        from repoforge.docs_generator import _infer_project_name
        assert callable(_infer_project_name)

    def test_prettify_name_importable(self):
        from repoforge.docs_generator import _prettify_name
        assert _prettify_name("my-cool-project") == "My Cool Project"

    def test_rel_importable(self):
        from repoforge.docs_generator import _rel
        assert callable(_rel)

    def test_make_logger_importable(self):
        from repoforge.docs_generator import _make_logger
        log = _make_logger(verbose=False)
        log("should not crash")  # silent logger


# ── line count verification ──────────────────────────────────────────────


class TestLineCountLimits:
    """Verify no refactored file exceeds the 400-line limit."""

    def test_docs_generator_under_limit(self):
        import repoforge.docs_generator as m
        lines = len(open(m.__file__).readlines())
        assert lines <= 400, f"docs_generator.py has {lines} lines (max 400)"

    def test_pipeline_files_under_limit(self):
        import repoforge.pipeline.context as ctx
        import repoforge.pipeline.generate as gen
        import repoforge.pipeline.write as wr

        for mod in [ctx, gen, wr]:
            lines = len(open(mod.__file__).readlines())
            assert lines <= 400, f"{mod.__name__} has {lines} lines (max 400)"

    def test_prompts_files_under_limit(self):
        import repoforge.docs_prompts.system as sys_mod
        import repoforge.docs_prompts.context as ctx_mod
        import repoforge.docs_prompts.builders as bld
        import repoforge.docs_prompts.builders_extra as bld_x
        import repoforge.docs_prompts.chapters as ch
        import repoforge.docs_prompts.classify as clf
        import repoforge.docs_prompts.adaptive as adp
        import repoforge.docs_prompts.monorepo as mono

        for mod in [sys_mod, ctx_mod, bld, bld_x, ch, clf, adp, mono]:
            lines = len(open(mod.__file__).readlines())
            assert lines <= 400, f"{mod.__name__} has {lines} lines (max 400)"
