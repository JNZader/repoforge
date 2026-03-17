"""
tests/test_disclosure.py — Tests for progressive disclosure utilities.

Tests cover:
- extract_tier() at each level (L1, L2, L3)
- Backward compatibility (no markers → returns full content)
- extract_frontmatter() parsing (simple, extended, nested, lists)
- build_discovery_index() with mock skills directory
- estimate_tokens() rough estimation
- has_tier_markers() / count_tier_markers() detection
- Scorer bonus for tier markers in agent_readiness
- CLI --disclosure flag integration
- Generator integration (disclosure parameter, DISCOVERY_INDEX.md)
- Prompt integration (tiered instructions appended)
"""

import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures: crafted SKILL.md content with tier markers
# ---------------------------------------------------------------------------

TIERED_SKILL = """\
---
name: backend-layer
description: >
  FastAPI backend patterns for REST API development.
  Trigger: When working in backend/ directory.
complexity: medium
token_estimate: 1800
dependencies: []
related_skills: [database, auth]
load_priority: high
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

<!-- L1:START -->
# backend

FastAPI backend patterns for REST API development.

**Trigger**: When working in backend/ directory.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| New endpoint | `@router.get("/path")` |
| Auth check | `Depends(get_current_user)` |
| Run tests | `pytest tests/` |

## Critical Patterns (Summary)
- **Dependency Injection**: Always inject auth via `Depends()`
- **Pydantic Validation**: Use schemas for all request/response models
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Dependency Injection for Auth

Always inject the auth dependency instead of checking manually.

```python
from app.auth import get_current_user
from fastapi import Depends

@router.get("/users")
async def get_users(user=Depends(get_current_user)):
    return await UserService.list()
```

### Pydantic Validation

Use schemas for request validation.

```python
from app.models import UserCreate

@router.post("/users")
async def create_user(data: UserCreate):
    return await UserService.create(data)
```

## When to Use

- Adding new REST endpoints to `backend/routers/`
- Modifying authentication flow in `backend/auth.py`
- Debugging API response issues

## Commands

```bash
pytest tests/test_backend.py -v
ruff check backend/
```

## Anti-Patterns

### Don't: bypass auth middleware

Never access user data without going through the auth dependency.

```python
# BAD - no auth check
@router.get("/users/{user_id}")
async def get_user(user_id: int):
    return await db.get(user_id)
```
<!-- L3:END -->
"""

LEGACY_SKILL = """\
---
name: add-user-endpoint
description: >
  Patterns for user REST endpoints.
  Trigger: When working with users API.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Use dependency injection

Always inject auth dependency.

```python
@router.get("/users")
async def get_users(user=Depends(get_current_user)):
    return await UserService.list()
```

## When to Use

- Adding user endpoints

## Commands

```bash
pytest tests/
```

## Anti-Patterns

### Don't: skip auth

Never bypass authentication.

## Quick Reference

| Task | Pattern |
|------|---------|
| New endpoint | `@router.get("/path")` |
"""

PARTIAL_MARKERS = """\
---
name: partial
description: Only has L1 markers.
---

<!-- L1:START -->
# partial

Only has L1 markers, no L2 or L3.

**Trigger**: When testing partial markers.
<!-- L1:END -->

The rest of the content has no tier markers.
## Some Section

Some content without markers.
"""

MINIMAL_FRONTMATTER = """\
---
name: test
description: A test skill.
---

## Content
"""

EXTENDED_FRONTMATTER = """\
---
name: backend-layer
description: >
  FastAPI backend patterns.
  Trigger: When working in backend/.
complexity: high
token_estimate: 2500
dependencies: [database-layer, auth-layer]
related_skills: [frontend, shared]
load_priority: high
license: Apache-2.0
metadata:
  author: repoforge
  version: "2.0"
---

## Content
"""


# ---------------------------------------------------------------------------
# Tests: extract_tier
# ---------------------------------------------------------------------------

class TestExtractTier:
    def test_level1_returns_frontmatter_and_l1(self):
        from repoforge.disclosure import extract_tier
        result = extract_tier(TIERED_SKILL, level=1)
        # Should contain frontmatter
        assert "---" in result
        assert "name: backend-layer" in result
        # Should contain L1 content
        assert "# backend" in result
        assert "**Trigger**:" in result
        # Should NOT contain L2 or L3 content
        assert "## Quick Reference" not in result
        assert "## Critical Patterns (Detailed)" not in result
        assert "## Anti-Patterns" not in result

    def test_level2_returns_frontmatter_l1_l2(self):
        from repoforge.disclosure import extract_tier
        result = extract_tier(TIERED_SKILL, level=2)
        # Should contain frontmatter + L1 + L2
        assert "name: backend-layer" in result
        assert "# backend" in result
        assert "## Quick Reference" in result
        assert "## Critical Patterns (Summary)" in result
        # Should NOT contain L3
        assert "## Critical Patterns (Detailed)" not in result
        assert "## Anti-Patterns" not in result

    def test_level3_returns_full_content(self):
        from repoforge.disclosure import extract_tier
        result = extract_tier(TIERED_SKILL, level=3)
        # Should contain everything
        assert "name: backend-layer" in result
        assert "# backend" in result
        assert "## Quick Reference" in result
        assert "## Critical Patterns (Detailed)" in result
        assert "## Anti-Patterns" in result
        assert "## Commands" in result

    def test_no_markers_returns_full_content(self):
        from repoforge.disclosure import extract_tier
        result = extract_tier(LEGACY_SKILL, level=1)
        # Backward compatible: no markers → full content
        assert result == LEGACY_SKILL

    def test_no_markers_level2_returns_full(self):
        from repoforge.disclosure import extract_tier
        result = extract_tier(LEGACY_SKILL, level=2)
        assert result == LEGACY_SKILL

    def test_no_markers_level3_returns_full(self):
        from repoforge.disclosure import extract_tier
        result = extract_tier(LEGACY_SKILL, level=3)
        assert result == LEGACY_SKILL

    def test_invalid_level_raises(self):
        from repoforge.disclosure import extract_tier
        with pytest.raises(ValueError, match="level must be 1, 2, or 3"):
            extract_tier(TIERED_SKILL, level=0)
        with pytest.raises(ValueError, match="level must be 1, 2, or 3"):
            extract_tier(TIERED_SKILL, level=4)

    def test_empty_content(self):
        from repoforge.disclosure import extract_tier
        result = extract_tier("", level=1)
        assert result == ""

    def test_partial_markers_l1_works(self):
        from repoforge.disclosure import extract_tier
        result = extract_tier(PARTIAL_MARKERS, level=1)
        assert "# partial" in result
        assert "**Trigger**:" in result

    def test_partial_markers_l2_returns_only_l1(self):
        from repoforge.disclosure import extract_tier
        result = extract_tier(PARTIAL_MARKERS, level=2)
        # L2 markers don't exist, so only L1 content returned
        assert "# partial" in result
        # But should still have frontmatter + L1
        assert "name: partial" in result

    def test_level1_is_small(self):
        from repoforge.disclosure import extract_tier, estimate_tokens
        result = extract_tier(TIERED_SKILL, level=1)
        tokens = estimate_tokens(result)
        # L1 should be lightweight (~50-200 tokens including frontmatter)
        assert tokens < 400

    def test_level2_is_medium(self):
        from repoforge.disclosure import extract_tier, estimate_tokens
        result = extract_tier(TIERED_SKILL, level=2)
        tokens = estimate_tokens(result)
        # L2 adds quick reference but is still compact
        assert tokens < 800

    def test_tier_markers_stripped_from_output(self):
        from repoforge.disclosure import extract_tier
        result = extract_tier(TIERED_SKILL, level=3)
        # Tier markers should not be in the extracted content
        # (they're used as delimiters, not content)
        assert "<!-- L1:START -->" not in result
        assert "<!-- L1:END -->" not in result

    def test_frontmatter_always_present(self):
        from repoforge.disclosure import extract_tier
        for level in (1, 2, 3):
            result = extract_tier(TIERED_SKILL, level=level)
            assert "name: backend-layer" in result
            assert "complexity: medium" in result


# ---------------------------------------------------------------------------
# Tests: has_tier_markers / count_tier_markers
# ---------------------------------------------------------------------------

class TestTierMarkerDetection:
    def test_has_markers_true(self):
        from repoforge.disclosure import has_tier_markers
        assert has_tier_markers(TIERED_SKILL) is True

    def test_has_markers_false(self):
        from repoforge.disclosure import has_tier_markers
        assert has_tier_markers(LEGACY_SKILL) is False

    def test_has_markers_partial(self):
        from repoforge.disclosure import has_tier_markers
        assert has_tier_markers(PARTIAL_MARKERS) is True

    def test_has_markers_empty(self):
        from repoforge.disclosure import has_tier_markers
        assert has_tier_markers("") is False

    def test_count_markers_full(self):
        from repoforge.disclosure import count_tier_markers
        assert count_tier_markers(TIERED_SKILL) == 3

    def test_count_markers_none(self):
        from repoforge.disclosure import count_tier_markers
        assert count_tier_markers(LEGACY_SKILL) == 0

    def test_count_markers_partial(self):
        from repoforge.disclosure import count_tier_markers
        assert count_tier_markers(PARTIAL_MARKERS) == 1

    def test_count_markers_empty(self):
        from repoforge.disclosure import count_tier_markers
        assert count_tier_markers("") == 0


# ---------------------------------------------------------------------------
# Tests: extract_frontmatter
# ---------------------------------------------------------------------------

class TestExtractFrontmatter:
    def test_basic_fields(self):
        from repoforge.disclosure import extract_frontmatter
        fm = extract_frontmatter(MINIMAL_FRONTMATTER)
        assert fm["name"] == "test"
        assert fm["description"] == "A test skill."

    def test_extended_fields(self):
        from repoforge.disclosure import extract_frontmatter
        fm = extract_frontmatter(EXTENDED_FRONTMATTER)
        assert fm["name"] == "backend-layer"
        assert fm["complexity"] == "high"
        assert fm["token_estimate"] == "2500"
        assert fm["load_priority"] == "high"
        assert fm["license"] == "Apache-2.0"

    def test_list_values(self):
        from repoforge.disclosure import extract_frontmatter
        fm = extract_frontmatter(EXTENDED_FRONTMATTER)
        deps = fm.get("dependencies")
        assert isinstance(deps, list)
        assert "database-layer" in deps
        assert "auth-layer" in deps
        related = fm.get("related_skills")
        assert isinstance(related, list)
        assert "frontend" in related

    def test_multiline_description(self):
        from repoforge.disclosure import extract_frontmatter
        fm = extract_frontmatter(TIERED_SKILL)
        desc = fm.get("description", "")
        assert "FastAPI" in desc
        assert "Trigger:" in desc

    def test_nested_metadata(self):
        from repoforge.disclosure import extract_frontmatter
        fm = extract_frontmatter(EXTENDED_FRONTMATTER)
        assert fm.get("metadata.author") == "repoforge"
        assert fm.get("metadata.version") == "2.0"

    def test_no_frontmatter(self):
        from repoforge.disclosure import extract_frontmatter
        fm = extract_frontmatter("# Just a heading\n\nSome text.\n")
        assert fm == {}

    def test_empty_string(self):
        from repoforge.disclosure import extract_frontmatter
        fm = extract_frontmatter("")
        assert fm == {}

    def test_tiered_skill_frontmatter(self):
        from repoforge.disclosure import extract_frontmatter
        fm = extract_frontmatter(TIERED_SKILL)
        assert fm["name"] == "backend-layer"
        assert fm["complexity"] == "medium"
        assert fm["token_estimate"] == "1800"
        assert fm["load_priority"] == "high"
        deps = fm.get("dependencies")
        assert isinstance(deps, list)
        assert deps == []
        related = fm.get("related_skills")
        assert isinstance(related, list)
        assert "database" in related
        assert "auth" in related


# ---------------------------------------------------------------------------
# Tests: estimate_tokens
# ---------------------------------------------------------------------------

class TestEstimateTokens:
    def test_basic_estimation(self):
        from repoforge.disclosure import estimate_tokens
        # 100 chars → ~25 tokens
        assert estimate_tokens("a" * 100) == 25

    def test_empty_string(self):
        from repoforge.disclosure import estimate_tokens
        assert estimate_tokens("") == 0

    def test_real_content(self):
        from repoforge.disclosure import estimate_tokens
        tokens = estimate_tokens(TIERED_SKILL)
        # TIERED_SKILL is ~1500 chars → ~375 tokens
        assert 200 < tokens < 1000

    def test_short_content(self):
        from repoforge.disclosure import estimate_tokens
        assert estimate_tokens("hello") == 1

    def test_returns_int(self):
        from repoforge.disclosure import estimate_tokens
        result = estimate_tokens("test content")
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# Tests: build_discovery_index
# ---------------------------------------------------------------------------

class TestBuildDiscoveryIndex:
    @pytest.fixture
    def mock_skills_dir(self, tmp_path):
        """Create a directory structure with SKILL.md files."""
        backend = tmp_path / "backend"
        backend.mkdir()
        (backend / "SKILL.md").write_text(TIERED_SKILL, encoding="utf-8")

        users = tmp_path / "backend" / "users"
        users.mkdir()
        (users / "SKILL.md").write_text(LEGACY_SKILL, encoding="utf-8")

        frontend = tmp_path / "frontend"
        frontend.mkdir()
        (frontend / "SKILL.md").write_text(MINIMAL_FRONTMATTER, encoding="utf-8")

        return tmp_path

    def test_returns_markdown(self, mock_skills_dir):
        from repoforge.disclosure import build_discovery_index
        result = build_discovery_index(str(mock_skills_dir))
        assert isinstance(result, str)
        assert "# Skill Discovery Index" in result

    def test_contains_table(self, mock_skills_dir):
        from repoforge.disclosure import build_discovery_index
        result = build_discovery_index(str(mock_skills_dir))
        assert "| Name |" in result
        assert "| Description |" in result
        assert "| Trigger |" in result

    def test_lists_all_skills(self, mock_skills_dir):
        from repoforge.disclosure import build_discovery_index
        result = build_discovery_index(str(mock_skills_dir))
        assert "backend-layer" in result
        assert "add-user-endpoint" in result
        assert "test" in result

    def test_shows_complexity(self, mock_skills_dir):
        from repoforge.disclosure import build_discovery_index
        result = build_discovery_index(str(mock_skills_dir))
        # The tiered skill has complexity: medium
        assert "medium" in result

    def test_shows_token_estimate(self, mock_skills_dir):
        from repoforge.disclosure import build_discovery_index
        result = build_discovery_index(str(mock_skills_dir))
        # Tiered skill has token_estimate: 1800
        assert "1800" in result

    def test_shows_total_count(self, mock_skills_dir):
        from repoforge.disclosure import build_discovery_index
        result = build_discovery_index(str(mock_skills_dir))
        assert "Total skills" in result
        assert "3" in result

    def test_includes_howto(self, mock_skills_dir):
        from repoforge.disclosure import build_discovery_index
        result = build_discovery_index(str(mock_skills_dir))
        assert "How to Use" in result

    def test_empty_directory(self, tmp_path):
        from repoforge.disclosure import build_discovery_index
        result = build_discovery_index(str(tmp_path))
        assert "# Skill Discovery Index" in result
        assert "Total skills" in result
        assert "0" in result

    def test_handles_nonexistent_dir(self, tmp_path):
        from repoforge.disclosure import build_discovery_index
        result = build_discovery_index(str(tmp_path / "nonexistent"))
        assert "# Skill Discovery Index" in result

    def test_relative_paths(self, mock_skills_dir):
        from repoforge.disclosure import build_discovery_index
        result = build_discovery_index(str(mock_skills_dir))
        # Should contain relative paths, not absolute
        assert str(mock_skills_dir) not in result

    def test_trigger_extracted(self, mock_skills_dir):
        from repoforge.disclosure import build_discovery_index
        result = build_discovery_index(str(mock_skills_dir))
        # Trigger should be extracted from description
        assert "backend/" in result or "working in backend" in result.lower()


# ---------------------------------------------------------------------------
# Tests: Scorer integration — tier_markers check
# ---------------------------------------------------------------------------

class TestScorerTierBonus:
    @pytest.fixture
    def scorer(self):
        from repoforge.scorer import SkillScorer
        return SkillScorer()

    def test_tiered_skill_has_tier_markers_check(self, scorer):
        score = scorer._score_content(TIERED_SKILL, "test.md")
        checks = score.details["agent_readiness"]["checks"]
        assert "tier_markers" in checks
        assert checks["tier_markers"] is True

    def test_legacy_skill_no_tier_markers(self, scorer):
        score = scorer._score_content(LEGACY_SKILL, "test.md")
        checks = score.details["agent_readiness"]["checks"]
        assert "tier_markers" in checks
        assert checks["tier_markers"] is False

    def test_tiered_skill_scores_higher_agent_readiness(self, scorer):
        tiered_score = scorer._score_content(TIERED_SKILL, "test.md")
        legacy_score = scorer._score_content(LEGACY_SKILL, "test.md")
        # Tiered skill should score higher in agent_readiness
        # (all else being roughly equal, the tier_markers check adds a boost)
        assert tiered_score.agent_readiness >= legacy_score.agent_readiness

    def test_tier_markers_check_count(self, scorer):
        # agent_readiness now has 6 checks instead of 5
        score = scorer._score_content(TIERED_SKILL, "test.md")
        checks = score.details["agent_readiness"]["checks"]
        assert len(checks) == 6

    def test_overall_dimensions_still_valid(self, scorer):
        """Ensure the new check doesn't break overall scoring."""
        score = scorer._score_content(TIERED_SKILL, "test.md")
        assert 0.0 <= score.agent_readiness <= 1.0
        assert 0.0 <= score.overall <= 1.0


# ---------------------------------------------------------------------------
# Tests: CLI --disclosure flag
# ---------------------------------------------------------------------------

class TestCLIDisclosureFlag:
    def test_help_shows_disclosure(self):
        from click.testing import CliRunner
        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["skills", "--help"])
        assert result.exit_code == 0
        assert "--disclosure" in result.output
        assert "tiered" in result.output
        assert "full" in result.output

    def test_disclosure_tiered_dry_run(self, tmp_path):
        from click.testing import CliRunner
        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills", "-w", repo_dir,
            "-o", str(tmp_path / "out"),
            "--disclosure", "tiered",
            "--dry-run", "-q",
        ])
        assert result.exit_code == 0

    def test_disclosure_full_dry_run(self, tmp_path):
        from click.testing import CliRunner
        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills", "-w", repo_dir,
            "-o", str(tmp_path / "out"),
            "--disclosure", "full",
            "--dry-run", "-q",
        ])
        assert result.exit_code == 0

    def test_default_disclosure_is_tiered(self, tmp_path):
        from click.testing import CliRunner
        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills", "-w", repo_dir,
            "-o", str(tmp_path / "out"),
            "--dry-run", "-q",
        ])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Tests: Generator integration
# ---------------------------------------------------------------------------

class TestGeneratorDisclosureIntegration:
    def test_disclosure_in_result(self, tmp_path):
        """generate_artifacts should return disclosure mode in result."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            dry_run=True,
            verbose=False,
            disclosure="tiered",
        )
        assert result["disclosure"] == "tiered"

    def test_disclosure_full_in_result(self, tmp_path):
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            dry_run=True,
            verbose=False,
            disclosure="full",
        )
        assert result["disclosure"] == "full"

    def test_discovery_index_not_in_dry_run(self, tmp_path):
        """Dry run should not create DISCOVERY_INDEX.md."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            dry_run=True,
            verbose=False,
            disclosure="tiered",
        )
        # In dry-run, no files written, so no discovery_index
        assert "discovery_index" not in result


# ---------------------------------------------------------------------------
# Tests: Prompt integration
# ---------------------------------------------------------------------------

class TestPromptDisclosureIntegration:
    @pytest.fixture
    def sample_module(self):
        return {
            "path": "backend/routers/users.py",
            "name": "users",
            "language": "Python",
            "exports": ["get_users", "create_user"],
            "imports": ["fastapi"],
            "summary_hint": "User endpoints",
        }

    @pytest.fixture
    def sample_repo_map(self):
        return {
            "root": "/fake/project",
            "tech_stack": ["Python", "FastAPI"],
            "entry_points": ["backend/main.py"],
            "config_files": ["pyproject.toml"],
            "layers": {
                "backend": {
                    "path": "backend",
                    "modules": [
                        {
                            "path": "backend/routers/users.py",
                            "name": "users",
                            "language": "Python",
                            "exports": ["get_users", "create_user"],
                            "imports": ["fastapi"],
                            "summary_hint": "User endpoints",
                        },
                    ],
                }
            },
            "stats": {"total_files": 10},
        }

    def test_skill_prompt_tiered_has_tier_instructions(self, sample_module, sample_repo_map):
        from repoforge.prompts import skill_prompt
        _, user = skill_prompt(
            sample_module, "backend", sample_repo_map,
            disclosure="tiered",
        )
        assert "PROGRESSIVE DISCLOSURE" in user
        assert "L1:START" in user
        assert "L2:START" in user
        assert "L3:START" in user

    def test_skill_prompt_full_no_tier_instructions(self, sample_module, sample_repo_map):
        from repoforge.prompts import skill_prompt
        _, user = skill_prompt(
            sample_module, "backend", sample_repo_map,
            disclosure="full",
        )
        assert "PROGRESSIVE DISCLOSURE" not in user
        assert "L1:START" not in user

    def test_layer_prompt_tiered_has_tier_instructions(self, sample_repo_map):
        from repoforge.prompts import layer_skill_prompt
        layer = sample_repo_map["layers"]["backend"]
        _, user = layer_skill_prompt(
            "backend", layer, sample_repo_map,
            disclosure="tiered",
        )
        assert "PROGRESSIVE DISCLOSURE" in user
        assert "tier_estimate" in user or "token_estimate" in user

    def test_layer_prompt_full_no_tier_instructions(self, sample_repo_map):
        from repoforge.prompts import layer_skill_prompt
        layer = sample_repo_map["layers"]["backend"]
        _, user = layer_skill_prompt(
            "backend", layer, sample_repo_map,
            disclosure="full",
        )
        assert "PROGRESSIVE DISCLOSURE" not in user

    def test_tiered_mentions_complexity_field(self, sample_module, sample_repo_map):
        from repoforge.prompts import skill_prompt
        _, user = skill_prompt(
            sample_module, "backend", sample_repo_map,
            disclosure="tiered",
        )
        assert "complexity" in user
        assert "token_estimate" in user
        assert "dependencies" in user
        assert "related_skills" in user
        assert "load_priority" in user

    def test_default_disclosure_is_full(self, sample_module, sample_repo_map):
        """Default disclosure mode for prompt functions is 'full' (backward compatible)."""
        from repoforge.prompts import skill_prompt
        _, user = skill_prompt(sample_module, "backend", sample_repo_map)
        assert "PROGRESSIVE DISCLOSURE" not in user


# ---------------------------------------------------------------------------
# Tests: Edge cases and backward compatibility
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_extract_tier_preserves_frontmatter_across_levels(self):
        from repoforge.disclosure import extract_tier
        for level in (1, 2, 3):
            result = extract_tier(TIERED_SKILL, level=level)
            assert "name: backend-layer" in result

    def test_extract_tier_content_not_empty(self):
        from repoforge.disclosure import extract_tier
        for level in (1, 2, 3):
            result = extract_tier(TIERED_SKILL, level=level)
            assert len(result.strip()) > 0

    def test_extract_tier_levels_are_cumulative(self):
        from repoforge.disclosure import extract_tier, estimate_tokens
        l1 = extract_tier(TIERED_SKILL, level=1)
        l2 = extract_tier(TIERED_SKILL, level=2)
        l3 = extract_tier(TIERED_SKILL, level=3)
        # Each level should be progressively larger
        assert estimate_tokens(l1) < estimate_tokens(l2)
        assert estimate_tokens(l2) < estimate_tokens(l3)

    def test_legacy_skill_no_degradation(self):
        """Skills without markers must work identically everywhere."""
        from repoforge.disclosure import extract_tier, has_tier_markers
        assert has_tier_markers(LEGACY_SKILL) is False
        for level in (1, 2, 3):
            result = extract_tier(LEGACY_SKILL, level=level)
            assert result == LEGACY_SKILL

    def test_frontmatter_empty_list(self):
        from repoforge.disclosure import extract_frontmatter
        fm = extract_frontmatter(TIERED_SKILL)
        deps = fm.get("dependencies")
        assert isinstance(deps, list)
        assert deps == []

    def test_only_whitespace_content(self):
        from repoforge.disclosure import extract_tier
        result = extract_tier("   \n\n   ", level=1)
        assert result == "   \n\n   "

    def test_build_discovery_index_with_bad_files(self, tmp_path):
        """Skills with no frontmatter should be skipped gracefully."""
        from repoforge.disclosure import build_discovery_index
        (tmp_path / "bad").mkdir()
        (tmp_path / "bad" / "SKILL.md").write_text("No frontmatter here.\n", encoding="utf-8")
        result = build_discovery_index(str(tmp_path))
        # Should not crash, just skip the bad skill
        assert "# Skill Discovery Index" in result
        assert "Total skills" in result
