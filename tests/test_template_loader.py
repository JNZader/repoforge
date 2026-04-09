"""Tests for YAML chapter template loader — Phase 1 Foundation.

Covers:
- Task 1.3: ConditionEvaluator (all 6 predicates, compound AND/OR, edge cases, injection)
- Task 1.4: TemplateLoader (discovery, loading, validation, caching, fallback)
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from repoforge.ir.repo import LayerInfo, ModuleInfo, RepoMap
from repoforge.template_loader import (
    VALID_PROMPT_KEYS,
    ChapterDef,
    ChapterTemplate,
    ConditionError,
    ConditionEvaluator,
    TemplateLoader,
    TemplateValidationError,
    clear_cache,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def basic_repo_map() -> RepoMap:
    """A minimal RepoMap for condition testing."""
    return RepoMap(
        root="/tmp/test-project",
        tech_stack=["python", "django", "react"],
        layers={
            "backend": LayerInfo(
                path="backend",
                modules=[
                    ModuleInfo(path="backend/views.py", name="views.py", language="python"),
                    ModuleInfo(path="backend/models.py", name="models.py", language="python"),
                ],
            ),
            "frontend": LayerInfo(
                path="frontend",
                modules=[
                    ModuleInfo(path="frontend/App.tsx", name="App.tsx", language="typescript"),
                    ModuleInfo(path="frontend/routes/index.tsx", name="index.tsx", language="typescript"),
                ],
            ),
        },
        entry_points=["backend/manage.py"],
        config_files=["pyproject.toml", "docker-compose.yaml", "tsconfig.json"],
        repoforge_config={},
        stats={"total_files": 42},
    )


@pytest.fixture()
def empty_repo_map() -> RepoMap:
    """A RepoMap with no tech stack, layers, or files."""
    return RepoMap(
        root="/tmp/empty",
        tech_stack=[],
        layers={},
        entry_points=[],
        config_files=[],
        repoforge_config={},
        stats={"total_files": 0},
    )


@pytest.fixture(autouse=True)
def _clear_template_cache():
    """Ensure each test starts with a clean template cache."""
    clear_cache()
    yield
    clear_cache()


def _write_yaml(path: Path, data: dict) -> Path:
    """Helper: write a dict as YAML to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(data, f)
    return path


def _valid_template_dict(
    name: str = "Test Template",
    project_type: str = "web_service",
    chapters: list[dict] | None = None,
) -> dict:
    """Return a valid template dict for testing."""
    if chapters is None:
        chapters = [
            {
                "file": "04-core-mechanisms.md",
                "title": "Core Mechanisms",
                "description": "Request lifecycle, middleware, auth",
                "prompt_key": "core_mechanisms",
            },
        ]
    return {
        "name": name,
        "project_type": project_type,
        "chapters": chapters,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Task 1.3: ConditionEvaluator Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestConditionEvaluatorHasTech:
    """has_tech predicate tests."""

    def test_match_exact(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("has_tech('django')", basic_repo_map) is True

    def test_match_case_insensitive(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("has_tech('Django')", basic_repo_map) is True
        assert ConditionEvaluator.evaluate("has_tech('REACT')", basic_repo_map) is True

    def test_no_match(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("has_tech('rust')", basic_repo_map) is False

    def test_empty_tech_stack(self, empty_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("has_tech('python')", empty_repo_map) is False

    def test_partial_match(self, basic_repo_map: RepoMap):
        """has_tech uses substring match (like classify.py does)."""
        assert ConditionEvaluator.evaluate("has_tech('react')", basic_repo_map) is True

    def test_double_quotes(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate('has_tech("django")', basic_repo_map) is True


class TestConditionEvaluatorHasConfig:
    """has_config predicate tests."""

    def test_match(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("has_config('pyproject.toml')", basic_repo_map) is True

    def test_substring_match(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("has_config('docker')", basic_repo_map) is True

    def test_no_match(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("has_config('Cargo.toml')", basic_repo_map) is False

    def test_empty_configs(self, empty_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("has_config('any')", empty_repo_map) is False


class TestConditionEvaluatorHasPathMatch:
    """has_path_match predicate tests (glob via fnmatch)."""

    def test_match_glob(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("has_path_match('*.tsx')", basic_repo_map) is True

    def test_match_deep_glob(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("has_path_match('frontend/*.tsx')", basic_repo_map) is True

    def test_no_match(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("has_path_match('*.rs')", basic_repo_map) is False

    def test_empty_layers(self, empty_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("has_path_match('*')", empty_repo_map) is False

    def test_case_insensitive(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("has_path_match('*.TSX')", basic_repo_map) is True


class TestConditionEvaluatorHasLayer:
    """has_layer predicate tests."""

    def test_match(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("has_layer('backend')", basic_repo_map) is True

    def test_no_match(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("has_layer('infra')", basic_repo_map) is False

    def test_empty(self, empty_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("has_layer('any')", empty_repo_map) is False


class TestConditionEvaluatorLayerCount:
    """layer_count comparison tests."""

    def test_gte_true(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("layer_count >= 2", basic_repo_map) is True

    def test_gte_false(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("layer_count >= 5", basic_repo_map) is False

    def test_gt(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("layer_count > 1", basic_repo_map) is True
        assert ConditionEvaluator.evaluate("layer_count > 2", basic_repo_map) is False

    def test_lt(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("layer_count < 3", basic_repo_map) is True
        assert ConditionEvaluator.evaluate("layer_count < 2", basic_repo_map) is False

    def test_eq(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("layer_count == 2", basic_repo_map) is True
        assert ConditionEvaluator.evaluate("layer_count == 3", basic_repo_map) is False

    def test_ne(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("layer_count != 0", basic_repo_map) is True

    def test_zero_layers(self, empty_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("layer_count == 0", empty_repo_map) is True


class TestConditionEvaluatorTotalFiles:
    """total_files comparison tests."""

    def test_gte(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("total_files >= 42", basic_repo_map) is True
        assert ConditionEvaluator.evaluate("total_files >= 43", basic_repo_map) is False

    def test_eq(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("total_files == 42", basic_repo_map) is True

    def test_zero(self, empty_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("total_files == 0", empty_repo_map) is True


class TestConditionEvaluatorCompound:
    """Compound condition tests (AND / OR)."""

    def test_and_both_true(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate(
            "has_tech('django') and has_layer('backend')", basic_repo_map
        ) is True

    def test_and_one_false(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate(
            "has_tech('django') and has_tech('rust')", basic_repo_map
        ) is False

    def test_or_one_true(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate(
            "has_tech('rust') or has_tech('django')", basic_repo_map
        ) is True

    def test_or_both_false(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate(
            "has_tech('rust') or has_tech('elixir')", basic_repo_map
        ) is False

    def test_and_or_mixed(self, basic_repo_map: RepoMap):
        # "or" has lower precedence: A and B or C => (A and B) or C
        assert ConditionEvaluator.evaluate(
            "has_tech('rust') and has_tech('django') or has_layer('frontend')",
            basic_repo_map,
        ) is True

    def test_triple_and(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate(
            "has_tech('django') and has_layer('backend') and total_files >= 10",
            basic_repo_map,
        ) is True

    def test_comparison_in_compound(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate(
            "layer_count >= 2 and total_files > 10", basic_repo_map
        ) is True


class TestConditionEvaluatorEdgeCases:
    """Edge cases and safety tests."""

    def test_empty_condition_returns_true(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("", basic_repo_map) is True
        assert ConditionEvaluator.evaluate("  ", basic_repo_map) is True

    def test_none_condition_returns_true(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate(None, basic_repo_map) is True  # type: ignore[arg-type]

    def test_whitespace_is_stripped(self, basic_repo_map: RepoMap):
        assert ConditionEvaluator.evaluate("  has_tech('django')  ", basic_repo_map) is True

    def test_injection_eval_rejected(self, basic_repo_map: RepoMap):
        with pytest.raises(ConditionError):
            ConditionEvaluator.evaluate("eval('import os')", basic_repo_map)

    def test_injection_exec_rejected(self, basic_repo_map: RepoMap):
        with pytest.raises(ConditionError):
            ConditionEvaluator.evaluate('exec("rm -rf /")', basic_repo_map)

    def test_injection_import_rejected(self, basic_repo_map: RepoMap):
        with pytest.raises(ConditionError):
            ConditionEvaluator.evaluate("__import__('os').system('ls')", basic_repo_map)

    def test_unknown_function_rejected(self, basic_repo_map: RepoMap):
        with pytest.raises(ConditionError):
            ConditionEvaluator.evaluate("unknown_func('test')", basic_repo_map)

    def test_arbitrary_python_rejected(self, basic_repo_map: RepoMap):
        with pytest.raises(ConditionError):
            ConditionEvaluator.evaluate("1 + 1 == 2", basic_repo_map)

    def test_nonsense_string_rejected(self, basic_repo_map: RepoMap):
        with pytest.raises(ConditionError):
            ConditionEvaluator.evaluate("foobar", basic_repo_map)


# ══════════════════════════════════════════════════════════════════════════════
# Task 1.4: TemplateLoader Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestTemplateLoaderDiscovery:
    """Template discovery from directories."""

    def test_discover_from_extra_dir(self, tmp_path: Path):
        _write_yaml(tmp_path / "templates" / "web.yaml", _valid_template_dict())
        loader = TemplateLoader(extra_dirs=[tmp_path / "templates"])
        paths = loader.discover()
        assert len(paths) >= 1
        assert any(p.name == "web.yaml" for p in paths)

    def test_discover_empty_dir(self, tmp_path: Path):
        (tmp_path / "empty").mkdir()
        loader = TemplateLoader(extra_dirs=[tmp_path / "empty"])
        # May find built-in templates, but extra dir contributes 0
        extra_only = [p for p in loader.discover() if tmp_path in p.parents]
        assert extra_only == []

    def test_discover_nonexistent_dir(self):
        loader = TemplateLoader(extra_dirs=[Path("/tmp/does-not-exist-abc")])
        # Should not raise, just skip
        paths = loader.discover()
        assert isinstance(paths, list)

    def test_discover_yml_extension(self, tmp_path: Path):
        _write_yaml(tmp_path / "templates" / "test.yml", _valid_template_dict())
        loader = TemplateLoader(extra_dirs=[tmp_path / "templates"])
        paths = loader.discover()
        assert any(p.suffix == ".yml" for p in paths)


class TestTemplateLoaderValidation:
    """Template validation on load."""

    def test_valid_template_loads(self, tmp_path: Path):
        tpl_dict = _valid_template_dict(
            chapters=[
                {
                    "file": "04-core-mechanisms.md",
                    "title": "Core Mechanisms",
                    "description": "Request lifecycle",
                    "prompt_key": "core_mechanisms",
                },
                {
                    "file": "05-data-models.md",
                    "title": "Data Models",
                    "description": "Schemas and entities",
                    "prompt_key": "data_models",
                },
            ]
        )
        _write_yaml(tmp_path / "web.yaml", tpl_dict)
        loader = TemplateLoader(extra_dirs=[tmp_path])
        loader.load_all()
        tpl = loader.get("web_service")
        assert tpl is not None
        assert tpl.name == "Test Template"
        assert tpl.project_type == "web_service"
        assert len(tpl.chapters) == 2
        assert tpl.chapters[0].file == "04-core-mechanisms.md"
        assert tpl.chapters[0].prompt_key == "core_mechanisms"

    def test_missing_name_raises(self, tmp_path: Path):
        bad = {"project_type": "generic", "chapters": []}
        _write_yaml(tmp_path / "bad.yaml", bad)
        loader = TemplateLoader(extra_dirs=[tmp_path])
        with pytest.raises(TemplateValidationError, match="missing required field 'name'"):
            loader.load_all()

    def test_missing_project_type_raises(self, tmp_path: Path):
        bad = {"name": "Test", "chapters": []}
        _write_yaml(tmp_path / "bad.yaml", bad)
        loader = TemplateLoader(extra_dirs=[tmp_path])
        with pytest.raises(TemplateValidationError, match="missing required field 'project_type'"):
            loader.load_all()

    def test_missing_chapters_raises(self, tmp_path: Path):
        bad = {"name": "Test", "project_type": "generic"}
        _write_yaml(tmp_path / "bad.yaml", bad)
        loader = TemplateLoader(extra_dirs=[tmp_path])
        with pytest.raises(TemplateValidationError, match="missing required field 'chapters'"):
            loader.load_all()

    def test_chapter_missing_file_raises(self, tmp_path: Path):
        tpl = _valid_template_dict(chapters=[
            {"title": "Test", "description": "Desc", "prompt_key": "overview"},
        ])
        _write_yaml(tmp_path / "bad.yaml", tpl)
        loader = TemplateLoader(extra_dirs=[tmp_path])
        with pytest.raises(TemplateValidationError, match="missing required field 'file'"):
            loader.load_all()

    def test_chapter_missing_title_raises(self, tmp_path: Path):
        tpl = _valid_template_dict(chapters=[
            {"file": "04.md", "description": "Desc", "prompt_key": "overview"},
        ])
        _write_yaml(tmp_path / "bad.yaml", tpl)
        loader = TemplateLoader(extra_dirs=[tmp_path])
        with pytest.raises(TemplateValidationError, match="missing required field 'title'"):
            loader.load_all()

    def test_chapter_no_prompt_key_or_template_raises(self, tmp_path: Path):
        tpl = _valid_template_dict(chapters=[
            {"file": "04.md", "title": "Test", "description": "Desc"},
        ])
        _write_yaml(tmp_path / "bad.yaml", tpl)
        loader = TemplateLoader(extra_dirs=[tmp_path])
        with pytest.raises(TemplateValidationError, match="must have 'prompt_key' or 'prompt_template'"):
            loader.load_all()

    def test_invalid_prompt_key_raises(self, tmp_path: Path):
        tpl = _valid_template_dict(chapters=[
            {
                "file": "04.md",
                "title": "Test",
                "description": "Desc",
                "prompt_key": "nonexistent_function",
            },
        ])
        _write_yaml(tmp_path / "bad.yaml", tpl)
        loader = TemplateLoader(extra_dirs=[tmp_path])
        with pytest.raises(TemplateValidationError, match="invalid prompt_key 'nonexistent_function'"):
            loader.load_all()

    def test_prompt_template_accepted(self, tmp_path: Path):
        tpl = _valid_template_dict(chapters=[
            {
                "file": "05-custom.md",
                "title": "Custom",
                "description": "A custom chapter",
                "prompt_template": "Generate docs for {project_name}",
            },
        ])
        _write_yaml(tmp_path / "custom.yaml", tpl)
        loader = TemplateLoader(extra_dirs=[tmp_path])
        loader.load_all()
        result = loader.get("web_service")
        assert result is not None
        assert result.chapters[0].prompt_template == "Generate docs for {project_name}"

    def test_unknown_project_type_accepted(self, tmp_path: Path):
        """Custom project types are allowed (spec: unknown type accepted as custom)."""
        tpl = _valid_template_dict(project_type="embedded_firmware")
        _write_yaml(tmp_path / "firmware.yaml", tpl)
        loader = TemplateLoader(extra_dirs=[tmp_path])
        loader.load_all()
        result = loader.get("embedded_firmware")
        assert result is not None
        assert result.project_type == "embedded_firmware"

    def test_invalid_yaml_raises(self, tmp_path: Path):
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("- this\n  is: [broken yaml\n  haha")
        loader = TemplateLoader(extra_dirs=[tmp_path])
        with pytest.raises(Exception):
            loader.load_all()

    def test_non_dict_yaml_raises(self, tmp_path: Path):
        """A YAML file that parses to a list instead of a dict."""
        list_file = tmp_path / "list.yaml"
        list_file.write_text("- item1\n- item2\n")
        loader = TemplateLoader(extra_dirs=[tmp_path])
        with pytest.raises(TemplateValidationError, match="must be a YAML mapping"):
            loader.load_all()

    def test_model_field_parsed(self, tmp_path: Path):
        """YAML chapter with model field is parsed into ChapterDef."""
        tpl = _valid_template_dict(chapters=[
            {
                "file": "04-core-mechanisms.md",
                "title": "Core",
                "description": "Desc",
                "prompt_key": "core_mechanisms",
                "model": "cli/claude",
            },
        ])
        _write_yaml(tmp_path / "m.yaml", tpl)
        loader = TemplateLoader(extra_dirs=[tmp_path])
        loader.load_all()
        result = loader.get("web_service")
        assert result is not None
        assert result.chapters[0].model == "cli/claude"
        assert result.chapters[0].model_tier is None

    def test_model_tier_field_parsed(self, tmp_path: Path):
        """YAML chapter with model_tier field is parsed into ChapterDef."""
        tpl = _valid_template_dict(chapters=[
            {
                "file": "04-core-mechanisms.md",
                "title": "Core",
                "description": "Desc",
                "prompt_key": "core_mechanisms",
                "model_tier": "heavy",
            },
        ])
        _write_yaml(tmp_path / "mt.yaml", tpl)
        loader = TemplateLoader(extra_dirs=[tmp_path])
        loader.load_all()
        result = loader.get("web_service")
        assert result is not None
        assert result.chapters[0].model is None
        assert result.chapters[0].model_tier == "heavy"

    def test_condition_with_valid_syntax(self, tmp_path: Path):
        tpl = _valid_template_dict(chapters=[
            {
                "file": "04.md",
                "title": "Test",
                "description": "Desc",
                "prompt_key": "core_mechanisms",
                "condition": "has_tech('react') and layer_count >= 2",
            },
        ])
        _write_yaml(tmp_path / "cond.yaml", tpl)
        loader = TemplateLoader(extra_dirs=[tmp_path])
        loader.load_all()
        result = loader.get("web_service")
        assert result is not None
        assert result.chapters[0].condition == "has_tech('react') and layer_count >= 2"

    def test_condition_with_invalid_syntax_raises(self, tmp_path: Path):
        tpl = _valid_template_dict(chapters=[
            {
                "file": "04.md",
                "title": "Test",
                "description": "Desc",
                "prompt_key": "core_mechanisms",
                "condition": "exec('evil')",
            },
        ])
        _write_yaml(tmp_path / "bad_cond.yaml", tpl)
        loader = TemplateLoader(extra_dirs=[tmp_path])
        with pytest.raises(ConditionError):
            loader.load_all()


class TestTemplateLoaderCaching:
    """Caching behavior tests."""

    def test_load_all_caches(self, tmp_path: Path):
        _write_yaml(tmp_path / "web.yaml", _valid_template_dict())
        loader = TemplateLoader(extra_dirs=[tmp_path])
        loader.load_all()
        tpl1 = loader.get("web_service")

        # Calling load_all again should not re-read files
        loader.load_all()
        tpl2 = loader.get("web_service")
        assert tpl1 is tpl2  # Same object from cache

    def test_get_triggers_load(self, tmp_path: Path):
        _write_yaml(tmp_path / "web.yaml", _valid_template_dict())
        loader = TemplateLoader(extra_dirs=[tmp_path])
        # get() without prior load_all() should auto-load
        tpl = loader.get("web_service")
        assert tpl is not None

    def test_clear_cache_works(self, tmp_path: Path):
        _write_yaml(
            tmp_path / "firmware.yaml",
            _valid_template_dict(name="Firmware", project_type="embedded_firmware"),
        )
        loader = TemplateLoader(extra_dirs=[tmp_path])
        loader.load_all()
        assert loader.get("embedded_firmware") is not None

        clear_cache()
        # After clearing, a NEW loader without that extra dir should NOT find it
        loader2 = TemplateLoader(extra_dirs=[])
        loader2.load_all()
        assert loader2.get("embedded_firmware") is None


class TestTemplateLoaderUserOverride:
    """User templates override built-in templates."""

    def test_user_overrides_builtin(self, tmp_path: Path):
        builtin_dir = tmp_path / "builtin"
        user_dir = tmp_path / "user"

        _write_yaml(
            builtin_dir / "web.yaml",
            _valid_template_dict(name="Built-in Web"),
        )
        _write_yaml(
            user_dir / "web.yaml",
            _valid_template_dict(name="User Web"),
        )

        # Simulate: first load built-in, then user
        loader = TemplateLoader(extra_dirs=[user_dir])
        # Manually load built-in first
        from repoforge.template_loader import _CACHE
        loader_builtin = TemplateLoader(extra_dirs=[builtin_dir])
        loader_builtin.load_all()
        assert _CACHE.get("web_service") is not None
        assert _CACHE["web_service"].name == "Built-in Web"

        # Now load user override
        clear_cache()
        # Load both: builtin loads first, user overrides
        _write_yaml(builtin_dir / "web.yaml", _valid_template_dict(name="Built-in Web"))
        _write_yaml(user_dir / "web.yaml", _valid_template_dict(name="User Web"))

        # Create a loader that loads builtin first, then user
        # We simulate by loading the user dir
        loader = TemplateLoader(extra_dirs=[builtin_dir, user_dir])
        loader.load_all()
        result = loader.get("web_service")
        assert result is not None
        assert result.name == "User Web"  # User wins


class TestTemplateLoaderMissingFallback:
    """Missing template returns None."""

    def test_get_nonexistent_type_returns_none(self, tmp_path: Path):
        _write_yaml(tmp_path / "web.yaml", _valid_template_dict())
        loader = TemplateLoader(extra_dirs=[tmp_path])
        loader.load_all()
        assert loader.get("nonexistent_type") is None

    def test_get_from_empty_loader_unknown_type(self):
        loader = TemplateLoader(extra_dirs=[])
        assert loader.get("totally_made_up_type") is None


class TestChapterDefDataclass:
    """ChapterDef frozen dataclass behavior."""

    def test_frozen(self):
        ch = ChapterDef(file="04.md", title="T", description="D", prompt_key="overview")
        with pytest.raises(AttributeError):
            ch.file = "other.md"  # type: ignore[misc]

    def test_defaults(self):
        ch = ChapterDef(file="04.md", title="T", description="D", prompt_key="overview")
        assert ch.prompt_template is None
        assert ch.condition is None
        assert ch.order == 0
        assert ch.model is None
        assert ch.model_tier is None

    def test_model_field(self):
        """ChapterDef stores explicit model string."""
        ch = ChapterDef(
            file="04.md", title="T", description="D",
            prompt_key="overview", model="gpt-4o",
        )
        assert ch.model == "gpt-4o"
        assert ch.model_tier is None

    def test_model_tier_field(self):
        """ChapterDef stores explicit model_tier string."""
        ch = ChapterDef(
            file="04.md", title="T", description="D",
            prompt_key="overview", model_tier="heavy",
        )
        assert ch.model is None
        assert ch.model_tier == "heavy"

    def test_both_model_and_tier(self):
        """ChapterDef accepts both model and model_tier."""
        ch = ChapterDef(
            file="04.md", title="T", description="D",
            prompt_key="overview", model="gpt-4o", model_tier="light",
        )
        assert ch.model == "gpt-4o"
        assert ch.model_tier == "light"


class TestChapterTemplateDataclass:
    """ChapterTemplate frozen dataclass behavior."""

    def test_frozen(self):
        tpl = ChapterTemplate(name="Test", project_type="generic")
        with pytest.raises(AttributeError):
            tpl.name = "Other"  # type: ignore[misc]

    def test_chapter_list_returns_list(self):
        chapters = (
            ChapterDef(file="a.md", title="A", description="D", prompt_key="overview"),
        )
        tpl = ChapterTemplate(name="T", project_type="generic", chapters=chapters)
        result = tpl.chapter_list
        assert isinstance(result, list)
        assert len(result) == 1

    def test_default_empty_chapters(self):
        tpl = ChapterTemplate(name="T", project_type="generic")
        assert tpl.chapters == ()


class TestValidPromptKeys:
    """Ensure VALID_PROMPT_KEYS matches what _dispatch_prompt handles."""

    def test_known_keys(self):
        expected = {
            "index", "overview", "quickstart", "architecture",
            "core_mechanisms", "data_models", "api_reference", "dev_guide",
        }
        assert VALID_PROMPT_KEYS == expected
