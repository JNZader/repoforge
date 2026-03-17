"""
tests/test_compressor.py — Tests for token compression.

Tests cover:
- Each compression pass individually
- Combined compression (normal + aggressive)
- YAML frontmatter preservation
- Code blocks not corrupted
- Tier markers (L1/L2/L3) preserved
- Compression ratio calculation
- Dry-run mode (via CLI)
- Report generation
- compress_file / compress_directory file I/O
- CLI compress subcommand
- CLI --compress flag on skills subcommand
- Generator integration (compress parameter)
- Edge cases (empty files, only frontmatter, large files)
"""

import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures: crafted content for testing compression passes
# ---------------------------------------------------------------------------

SKILL_WITH_FLUFF = """\
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

In order to understand this skill, it is important to note that the backend
layer handles all REST API development.

**Trigger**: When working in backend/ directory.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

|    Task       |    Pattern              |
|---------------|-------------------------|
|  New endpoint |  `@router.get("/path")` |
|  Auth check   |  `Depends(get_user)`    |
|  Run tests    |  `pytest tests/`        |

## Critical Patterns (Summary)
- **Dependency Injection**: You should consider using Depends() for auth
- **Pydantic Validation**: Make sure to always use schemas for request validation
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Dependency Injection for Auth

Please note that you should always inject the auth dependency instead of
checking manually. It is recommended that all endpoints use this pattern.

```python
from app.auth import get_current_user
from fastapi import Depends

# Import the auth module
# This is important for security

@router.get("/users")
async def get_users(user=Depends(get_current_user)):
    return await UserService.list()
```

### Pydantic Validation

In order to validate requests, make sure to use Pydantic schemas.
Due to the fact that FastAPI integrates tightly with Pydantic, this means that
you get automatic validation for free.

```python
from app.models import UserCreate

@router.post("/users")
async def create_user(data: UserCreate):
    return await UserService.create(data)
```

## When to Use

- Adding new REST endpoints to `backend/routers/`
  These endpoints should follow the patterns above
  and always use dependency injection.
- Modifying authentication flow in `backend/auth.py`
  Make sure to test after any auth changes.
- Debugging API response issues

## Commands

```bash
pytest tests/test_backend.py -v
ruff check backend/
```

## Anti-Patterns

### Don't: bypass auth middleware

Please be aware that you should never access user data
without going through the auth dependency.

```python
# BAD - no auth check
@router.get("/users/{user_id}")
async def get_user(user_id: int):
    return await db.get(user_id)
```

---

***

___

Some decorative separators above should be removed.
<!-- L3:END -->
"""

MINIMAL_SKILL = """\
---
name: test-skill
description: A minimal skill.
---

## Patterns

Some patterns here.
"""

CODE_ONLY_SKILL = """\
---
name: code-skill
description: Skill with code blocks.
---

## Code

```python
def hello():
    # This is a function
    # It does something important
    pass


# Another comment here

def world():
    pass
```

```bash
# Run tests
pytest tests/
```
"""

AGGRESSIVE_CONTENT = """\
---
name: test-aggressive
description: >
  Configuration of the authentication implementation.
  Trigger: When working with authentication configuration.
---

## Patterns

The application uses authentication for authorization of requests.
Each function in the implementation handles configuration of the
environment for development and production deployment.

The repository has dependencies that need configuration.

```python
# This code has the word configuration in it
def get_configuration():
    # authentication implementation
    return {"environment": "development"}
```

Outside code: configuration, authentication, implementation.
"""

MULTILINE_BULLETS = """\
---
name: bullets-test
description: Test bullet compression.
---

## Features

- Feature one is really cool
  and spans multiple lines
  with lots of detail
- Feature two is short
- Feature three
  also spans lines
  three lines total

## Commands

```bash
pytest tests/
```
"""

TABLE_PADDED = """\
---
name: table-test
description: Test table compression.
---

## Reference

|    Task       |    Pattern              |    Notes                  |
|:------------- |:-----------------------:| -------------------------:|
|  New endpoint |  `@router.get("/path")` |  Use router decorators    |
|  Auth check   |  `Depends(get_user)`    |  Always required          |
"""

WHITESPACE_HEAVY = """\
---
name: whitespace-test
description: Test whitespace compression.
---


## Section One


Content here.



## Section Two



More content here.    
With trailing spaces.   

"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def compressor():
    from repoforge.compressor import SkillCompressor
    return SkillCompressor()


@pytest.fixture
def skill_file(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(SKILL_WITH_FLUFF, encoding="utf-8")
    return p


@pytest.fixture
def skills_directory(tmp_path):
    (tmp_path / "layer-a").mkdir()
    (tmp_path / "layer-a" / "SKILL.md").write_text(SKILL_WITH_FLUFF, encoding="utf-8")
    (tmp_path / "layer-b").mkdir()
    (tmp_path / "layer-b" / "SKILL.md").write_text(MINIMAL_SKILL, encoding="utf-8")
    (tmp_path / "layer-c").mkdir()
    (tmp_path / "layer-c" / "SKILL.md").write_text(CODE_ONLY_SKILL, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Tests: Whitespace pass
# ---------------------------------------------------------------------------

class TestPassWhitespace:
    def test_removes_trailing_spaces(self, compressor):
        result = compressor._pass_whitespace("hello   \nworld   \n")
        assert "   \n" not in result

    def test_collapses_blank_lines(self, compressor):
        result = compressor._pass_whitespace("a\n\n\n\n\nb\n")
        assert "\n\n\n" not in result
        assert "a\n\nb\n" == result

    def test_ends_with_single_newline(self, compressor):
        result = compressor._pass_whitespace("hello\n\n\n")
        assert result.endswith("\n")
        assert not result.endswith("\n\n")

    def test_whitespace_heavy_input(self, compressor):
        result = compressor._pass_whitespace(WHITESPACE_HEAVY)
        # No trailing spaces
        for line in result.split("\n"):
            assert line == line.rstrip(), f"Trailing space in: {line!r}"
        # No triple newlines
        assert "\n\n\n" not in result

    def test_preserves_indentation(self, compressor):
        result = compressor._pass_whitespace("  indented\n    more indented\n")
        assert "  indented" in result
        assert "    more indented" in result


# ---------------------------------------------------------------------------
# Tests: Headers pass
# ---------------------------------------------------------------------------

class TestPassHeaders:
    def test_removes_decorative_separators(self, compressor):
        content = "## Section\n\n---\n\nContent\n\n***\n\nMore\n\n___\n"
        result = compressor._pass_headers(content)
        assert "---" not in result
        assert "***" not in result
        assert "___" not in result

    def test_preserves_yaml_frontmatter(self, compressor):
        content = "---\nname: test\n---\n\n---\n\nContent\n"
        result = compressor._pass_headers(content)
        # Frontmatter delimiters preserved
        assert result.startswith("---\nname: test\n---\n")
        # But decorative separator removed
        lines = result.split("\n")
        separator_count = sum(1 for ln in lines[3:] if ln.strip() == "---")
        assert separator_count == 0

    def test_preserves_content_headers(self, compressor):
        content = "---\nname: t\n---\n\n## Section One\n\n### Sub\n"
        result = compressor._pass_headers(content)
        assert "## Section One" in result
        assert "### Sub" in result


# ---------------------------------------------------------------------------
# Tests: Prose pass
# ---------------------------------------------------------------------------

class TestPassProse:
    def test_removes_filler_phrases(self, compressor):
        content = "---\nname: t\n---\n\nIn order to use this, please note that it works.\n"
        result = compressor._pass_prose(content)
        assert "In order to" not in result
        assert "please note that" not in result.lower()

    def test_simplifies_verbose_phrases(self, compressor):
        cases = [
            ("In order to do X", "To do X"),
            ("It is important to note that X", "Note: X"),
            ("Make sure to always use X", "Always use X"),
            ("You should consider using X", "Use X"),
            ("Due to the fact that X", "Because X"),
        ]
        for original, expected_fragment in cases:
            content = f"---\nname: t\n---\n\n{original}\n"
            result = compressor._pass_prose(content)
            # Check the expected fragment appears (case-insensitive start)
            body = result.split("---\n", 2)[-1].strip()
            assert expected_fragment.lower() in body.lower(), \
                f"Expected '{expected_fragment}' in compressed: {body!r}"

    def test_does_not_modify_code_blocks(self, compressor):
        content = (
            "---\nname: t\n---\n\n"
            "In order to use this:\n\n"
            "```python\n"
            "# In order to do X\n"
            "result = In_order_to()\n"
            "```\n"
        )
        result = compressor._pass_prose(content)
        # Prose outside code is modified
        assert "To use this" in result or "use this" in result
        # Code inside is preserved
        assert "# In order to do X" in result
        assert "In_order_to()" in result

    def test_does_not_modify_yaml_frontmatter(self, compressor):
        content = (
            "---\n"
            "name: in-order-to-test\n"
            "description: In order to test frontmatter preservation.\n"
            "---\n\n"
            "In order to use this skill.\n"
        )
        result = compressor._pass_prose(content)
        # Frontmatter preserved
        assert "name: in-order-to-test" in result
        assert "In order to test frontmatter preservation" in result
        # Prose modified
        body = result.split("---\n", 2)[-1].strip()
        assert not body.startswith("In order to")

    def test_cleans_double_spaces(self, compressor):
        content = "---\nname: t\n---\n\nYou should  always check.\n"
        result = compressor._pass_prose(content)
        assert "  " not in result.split("---\n", 2)[-1]


# ---------------------------------------------------------------------------
# Tests: Tables pass
# ---------------------------------------------------------------------------

class TestPassTables:
    def test_compacts_table_padding(self, compressor):
        result = compressor._pass_tables(TABLE_PADDED)
        # Check cells are trimmed
        assert "|New endpoint|" in result or "| New endpoint |" not in result
        # The padded version should be gone
        assert "|    Task       |" not in result

    def test_preserves_table_structure(self, compressor):
        result = compressor._pass_tables(TABLE_PADDED)
        # Still has table rows
        lines = [ln for ln in result.split("\n") if ln.strip().startswith("|")]
        assert len(lines) >= 3  # header + separator + data rows

    def test_normalizes_separator_row(self, compressor):
        content = "|:--- |:---:| ---:|\n"
        result = compressor._pass_tables(content)
        # Separator should be simplified
        assert "---" in result


# ---------------------------------------------------------------------------
# Tests: Code blocks pass
# ---------------------------------------------------------------------------

class TestPassCodeBlocks:
    def test_collapses_blank_lines_in_code(self, compressor):
        result = compressor._pass_code_blocks(CODE_ONLY_SKILL)
        # Multiple blank lines in code → single blank line
        assert "\n\n\n" not in result

    def test_preserves_code_content(self, compressor):
        result = compressor._pass_code_blocks(CODE_ONLY_SKILL)
        assert "def hello():" in result
        assert "def world():" in result
        assert "pytest tests/" in result

    def test_strips_trailing_whitespace_in_code(self, compressor):
        content = "```python\ndef foo():   \n    pass   \n```\n"
        result = compressor._pass_code_blocks(content)
        code_lines = result.split("\n")
        for line in code_lines:
            if line.strip() and not line.startswith("```"):
                assert line == line.rstrip()


# ---------------------------------------------------------------------------
# Tests: Bullets pass
# ---------------------------------------------------------------------------

class TestPassBullets:
    def test_collapses_multiline_bullets(self, compressor):
        result = compressor._pass_bullets(MULTILINE_BULLETS)
        # Multi-line bullets should be single lines
        assert "Feature one is really cool and spans multiple lines with lots of detail" in result
        assert "Feature three also spans lines three lines total" in result

    def test_preserves_single_line_bullets(self, compressor):
        result = compressor._pass_bullets(MULTILINE_BULLETS)
        assert "- Feature two is short" in result

    def test_does_not_merge_across_code_blocks(self, compressor):
        content = "- Bullet one\n```python\ndef foo(): pass\n```\n- Bullet two\n"
        result = compressor._pass_bullets(content)
        assert "- Bullet one" in result
        assert "- Bullet two" in result
        assert "def foo(): pass" in result


# ---------------------------------------------------------------------------
# Tests: Abbreviations pass (aggressive mode)
# ---------------------------------------------------------------------------

class TestPassAbbreviations:
    def test_abbreviates_in_aggressive_mode(self, compressor):
        result = compressor._pass_abbreviations(AGGRESSIVE_CONTENT, aggressive=True)
        # Prose should be abbreviated
        assert "config" in result.lower()
        assert "auth" in result.lower()
        assert "impl" in result.lower()

    def test_no_abbreviations_in_normal_mode(self, compressor):
        result = compressor._pass_abbreviations(AGGRESSIVE_CONTENT, aggressive=False)
        # Should be unchanged
        assert result == AGGRESSIVE_CONTENT

    def test_does_not_abbreviate_inside_code_blocks(self, compressor):
        result = compressor._pass_abbreviations(AGGRESSIVE_CONTENT, aggressive=True)
        # Code block content should be preserved
        assert 'def get_configuration():' in result
        assert '"environment": "development"' in result

    def test_does_not_abbreviate_yaml_frontmatter(self, compressor):
        result = compressor._pass_abbreviations(AGGRESSIVE_CONTENT, aggressive=True)
        # Frontmatter preserved
        assert "name: test-aggressive" in result
        # Description in frontmatter should be preserved
        assert "Configuration" in result.split("---\n", 2)[1] or \
               "authentication" in result.split("---\n", 2)[1]

    def test_abbreviates_prose_outside_protected(self, compressor):
        result = compressor._pass_abbreviations(AGGRESSIVE_CONTENT, aggressive=True)
        # Last line of prose (outside code) should be abbreviated
        assert "Outside code:" in result
        # Check that at least some abbreviation happened in prose
        last_section = result.split("Outside code:")[-1]
        assert "config" in last_section


# ---------------------------------------------------------------------------
# Tests: Combined compression
# ---------------------------------------------------------------------------

class TestCombinedCompression:
    def test_normal_compression_reduces_tokens(self, compressor):
        result = compressor.compress(SKILL_WITH_FLUFF, aggressive=False)
        assert result.compressed_tokens < result.original_tokens
        assert result.ratio < 1.0

    def test_aggressive_compression_reduces_more(self, compressor):
        normal = compressor.compress(AGGRESSIVE_CONTENT, aggressive=False)
        aggressive = compressor.compress(AGGRESSIVE_CONTENT, aggressive=True)
        assert aggressive.compressed_tokens <= normal.compressed_tokens

    def test_compression_result_fields(self, compressor):
        result = compressor.compress(SKILL_WITH_FLUFF)
        assert isinstance(result.original, str)
        assert isinstance(result.compressed, str)
        assert isinstance(result.original_tokens, int)
        assert isinstance(result.compressed_tokens, int)
        assert isinstance(result.ratio, float)
        assert result.original == SKILL_WITH_FLUFF
        assert result.compressed != SKILL_WITH_FLUFF  # should differ

    def test_ratio_calculation(self, compressor):
        result = compressor.compress(SKILL_WITH_FLUFF)
        expected_ratio = result.compressed_tokens / result.original_tokens
        assert abs(result.ratio - expected_ratio) < 0.001

    def test_empty_content(self, compressor):
        result = compressor.compress("")
        assert result.compressed_tokens == 0
        assert result.original_tokens == 0
        assert result.ratio == 1.0

    def test_minimal_content(self, compressor):
        result = compressor.compress(MINIMAL_SKILL)
        # Minimal content should still compress some whitespace
        assert result.compressed_tokens <= result.original_tokens


# ---------------------------------------------------------------------------
# Tests: YAML frontmatter preservation
# ---------------------------------------------------------------------------

class TestFrontmatterPreservation:
    def test_frontmatter_unchanged_after_compression(self, compressor):
        result = compressor.compress(SKILL_WITH_FLUFF)
        # Extract frontmatter from both
        import re
        orig_fm = re.match(r"^---\s*\n.*?\n---\s*\n", SKILL_WITH_FLUFF, re.DOTALL)
        comp_fm = re.match(r"^---\s*\n.*?\n---\s*\n", result.compressed, re.DOTALL)
        assert orig_fm is not None
        assert comp_fm is not None
        assert orig_fm.group() == comp_fm.group()

    def test_frontmatter_preserved_in_aggressive(self, compressor):
        result = compressor.compress(AGGRESSIVE_CONTENT, aggressive=True)
        assert "name: test-aggressive" in result.compressed
        # Frontmatter description should be preserved
        import re
        fm = re.match(r"^---\s*\n(.*?)\n---", result.compressed, re.DOTALL)
        assert fm is not None
        assert "Configuration" in fm.group(1) or "authentication" in fm.group(1)


# ---------------------------------------------------------------------------
# Tests: Tier markers preserved
# ---------------------------------------------------------------------------

class TestTierMarkerPreservation:
    def test_l1_markers_preserved(self, compressor):
        result = compressor.compress(SKILL_WITH_FLUFF)
        assert "<!-- L1:START -->" in result.compressed
        assert "<!-- L1:END -->" in result.compressed

    def test_l2_markers_preserved(self, compressor):
        result = compressor.compress(SKILL_WITH_FLUFF)
        assert "<!-- L2:START -->" in result.compressed
        assert "<!-- L2:END -->" in result.compressed

    def test_l3_markers_preserved(self, compressor):
        result = compressor.compress(SKILL_WITH_FLUFF)
        assert "<!-- L3:START -->" in result.compressed
        assert "<!-- L3:END -->" in result.compressed

    def test_tier_extraction_works_after_compression(self, compressor):
        """Compressed content should still work with disclosure extract_tier."""
        from repoforge.disclosure import extract_tier, has_tier_markers
        result = compressor.compress(SKILL_WITH_FLUFF)
        assert has_tier_markers(result.compressed)

        l1 = extract_tier(result.compressed, level=1)
        assert "# backend" in l1
        assert "**Trigger**:" in l1

        l2 = extract_tier(result.compressed, level=2)
        assert "## Quick Reference" in l2

        l3 = extract_tier(result.compressed, level=3)
        assert "## Critical Patterns (Detailed)" in l3


# ---------------------------------------------------------------------------
# Tests: Code blocks not corrupted
# ---------------------------------------------------------------------------

class TestCodeBlockIntegrity:
    def test_code_blocks_preserved_after_full_compression(self, compressor):
        result = compressor.compress(SKILL_WITH_FLUFF)
        # Python code blocks should be intact
        assert "async def get_users(user=Depends(get_current_user)):" in result.compressed
        assert "async def create_user(data: UserCreate):" in result.compressed
        assert "pytest tests/test_backend.py -v" in result.compressed

    def test_code_blocks_preserved_in_aggressive(self, compressor):
        result = compressor.compress(AGGRESSIVE_CONTENT, aggressive=True)
        assert 'def get_configuration():' in result.compressed
        assert '"environment": "development"' in result.compressed

    def test_code_fence_markers_preserved(self, compressor):
        result = compressor.compress(SKILL_WITH_FLUFF)
        assert "```python" in result.compressed
        assert "```bash" in result.compressed
        # Count code fences (must be even)
        import re
        fences = re.findall(r"^```", result.compressed, re.MULTILINE)
        assert len(fences) % 2 == 0


# ---------------------------------------------------------------------------
# Tests: compress_file and compress_directory
# ---------------------------------------------------------------------------

class TestFileIO:
    def test_compress_file_in_place(self, skill_file):
        from repoforge.compressor import compress_file
        original_size = skill_file.stat().st_size
        result = compress_file(str(skill_file))
        new_size = skill_file.stat().st_size
        assert new_size < original_size
        assert result.compressed_tokens < result.original_tokens

    def test_compress_file_content_matches(self, skill_file):
        from repoforge.compressor import compress_file
        result = compress_file(str(skill_file))
        written = skill_file.read_text(encoding="utf-8")
        assert written == result.compressed

    def test_compress_directory(self, skills_directory):
        from repoforge.compressor import compress_directory
        results = compress_directory(str(skills_directory))
        assert len(results) == 3  # 3 SKILL.md files

    def test_compress_directory_aggressive(self, skills_directory):
        from repoforge.compressor import compress_directory
        results = compress_directory(str(skills_directory), aggressive=True)
        assert len(results) == 3

    def test_compress_empty_directory(self, tmp_path):
        from repoforge.compressor import compress_directory
        results = compress_directory(str(tmp_path))
        assert results == []


# ---------------------------------------------------------------------------
# Tests: compression_report
# ---------------------------------------------------------------------------

class TestCompressionReport:
    def test_report_with_results(self, compressor):
        from repoforge.compressor import compression_report
        results = [
            compressor.compress(SKILL_WITH_FLUFF),
            compressor.compress(MINIMAL_SKILL),
        ]
        report = compression_report(results)
        assert "Token Compression Report" in report
        assert "Total:" in report
        assert "Files: 2" in report
        assert "Ratio:" in report

    def test_report_empty(self):
        from repoforge.compressor import compression_report
        report = compression_report([])
        assert "No files compressed" in report

    def test_report_shows_reduction(self, compressor):
        from repoforge.compressor import compression_report
        results = [compressor.compress(SKILL_WITH_FLUFF)]
        report = compression_report(results)
        assert "reduction" in report
        assert "saved" in report

    def test_report_shows_per_file_stats(self, compressor):
        from repoforge.compressor import compression_report
        results = [
            compressor.compress(SKILL_WITH_FLUFF),
            compressor.compress(MINIMAL_SKILL),
        ]
        report = compression_report(results)
        # Should have at least 2 per-file lines with → arrow
        arrow_lines = [ln for ln in report.split("\n") if "→" in ln]
        assert len(arrow_lines) >= 2


# ---------------------------------------------------------------------------
# Tests: CLI compress subcommand
# ---------------------------------------------------------------------------

class TestCLICompress:
    def test_compress_help(self):
        from click.testing import CliRunner
        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["compress", "--help"])
        assert result.exit_code == 0
        assert "--aggressive" in result.output
        assert "--dry-run" in result.output
        assert "--target-dir" in result.output
        assert "--workspace" in result.output or "-w" in result.output

    def test_compress_skills_directory(self, skills_directory):
        from click.testing import CliRunner
        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, [
            "compress", "--target-dir", str(skills_directory),
        ])
        assert result.exit_code == 0
        assert "Token Compression Report" in result.output

    def test_compress_dry_run(self, skills_directory):
        from click.testing import CliRunner
        from repoforge.cli import main

        # Read original content
        original_contents = {}
        for f in skills_directory.rglob("*.md"):
            original_contents[str(f)] = f.read_text(encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(main, [
            "compress", "--target-dir", str(skills_directory), "--dry-run",
        ])
        assert result.exit_code == 0

        # Verify files unchanged
        for fpath, orig in original_contents.items():
            assert Path(fpath).read_text(encoding="utf-8") == orig

    def test_compress_aggressive(self, skills_directory):
        from click.testing import CliRunner
        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, [
            "compress", "--target-dir", str(skills_directory), "--aggressive",
        ])
        assert result.exit_code == 0

    def test_compress_missing_directory(self, tmp_path):
        from click.testing import CliRunner
        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, [
            "compress", "-w", str(tmp_path),
        ])
        assert result.exit_code != 0

    def test_compress_empty_directory(self, tmp_path):
        from click.testing import CliRunner
        from repoforge.cli import main
        empty = tmp_path / "empty"
        empty.mkdir()
        runner = CliRunner()
        result = runner.invoke(main, [
            "compress", "--target-dir", str(empty),
        ])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Tests: CLI --compress flag on skills subcommand
# ---------------------------------------------------------------------------

class TestCLICompressFlag:
    def test_skills_help_shows_compress_flag(self):
        from click.testing import CliRunner
        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["skills", "--help"])
        assert "--compress" in result.output
        assert "--no-compress" in result.output
        assert "--aggressive" in result.output

    def test_skills_dry_run_with_compress(self, tmp_path):
        """--compress with --dry-run should not crash."""
        from click.testing import CliRunner
        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "skills", "-w", repo_dir,
            "-o", str(tmp_path / "out"),
            "--compress", "--dry-run", "-q",
        ])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Tests: Generator integration
# ---------------------------------------------------------------------------

class TestGeneratorIntegration:
    def test_compress_in_dry_run_result(self, tmp_path):
        """generate_artifacts with compress=True, dry_run=True should not crash."""
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            dry_run=True,
            verbose=False,
            compress=True,
        )
        # In dry-run, compression is skipped
        assert "compression" not in result

    def test_compress_false_no_compression_key(self, tmp_path):
        from repoforge.generator import generate_artifacts
        repo_dir = str(Path(__file__).parent.parent)
        result = generate_artifacts(
            working_dir=repo_dir,
            output_dir=str(tmp_path / "out"),
            dry_run=True,
            verbose=False,
            compress=False,
        )
        assert "compression" not in result


# ---------------------------------------------------------------------------
# Tests: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_string(self, compressor):
        result = compressor.compress("")
        assert result.compressed == "\n"  # ends with newline after whitespace pass
        assert result.original_tokens == 0

    def test_only_frontmatter(self, compressor):
        content = "---\nname: test\ndescription: Test.\n---\n"
        result = compressor.compress(content)
        assert "name: test" in result.compressed
        assert "description: Test." in result.compressed

    def test_no_code_blocks(self, compressor):
        content = "---\nname: t\n---\n\n## Section\n\nJust prose here.\n"
        result = compressor.compress(content)
        assert "Just prose here." in result.compressed

    def test_all_dimensions_between_0_and_1(self, compressor):
        for content in [SKILL_WITH_FLUFF, MINIMAL_SKILL, CODE_ONLY_SKILL,
                        AGGRESSIVE_CONTENT, MULTILINE_BULLETS]:
            result = compressor.compress(content)
            assert 0.0 <= result.ratio <= 1.0

    def test_compression_is_deterministic(self, compressor):
        r1 = compressor.compress(SKILL_WITH_FLUFF)
        r2 = compressor.compress(SKILL_WITH_FLUFF)
        assert r1.compressed == r2.compressed
        assert r1.compressed_tokens == r2.compressed_tokens
        assert r1.ratio == r2.ratio

    def test_idempotent_compression(self, compressor):
        """Compressing twice should produce same result as compressing once."""
        first = compressor.compress(SKILL_WITH_FLUFF)
        second = compressor.compress(first.compressed)
        assert second.compressed == first.compressed

    def test_large_content_no_crash(self, compressor):
        # Generate a large content string
        large = "---\nname: big\n---\n\n"
        large += ("## Section\n\nIn order to do X, you should consider using Y.\n\n") * 100
        large += "```python\ndef foo(): pass\n```\n" * 50
        result = compressor.compress(large)
        assert result.compressed_tokens < result.original_tokens


# ---------------------------------------------------------------------------
# Tests: Public API exports
# ---------------------------------------------------------------------------

class TestPublicAPI:
    def test_imports_from_init(self):
        from repoforge import SkillCompressor, CompressionResult, compress_file, compress_directory
        assert SkillCompressor is not None
        assert CompressionResult is not None
        assert compress_file is not None
        assert compress_directory is not None

    def test_compressor_in_all(self):
        import repoforge
        assert "SkillCompressor" in repoforge.__all__
        assert "CompressionResult" in repoforge.__all__
        assert "compress_file" in repoforge.__all__
        assert "compress_directory" in repoforge.__all__
