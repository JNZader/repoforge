"""Tests for repoforge.intelligence.post_process — Stage D deterministic corrections."""

from __future__ import annotations

import pytest

from repoforge.facts import FactItem
from repoforge.intelligence.build_parser import BuildInfo
from repoforge.intelligence.ast_extractor import ASTSymbol
from repoforge.intelligence.post_process import post_process_chapter, Correction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _fact(fact_type: str, value: str, file: str = "server.go", line: int = 10) -> FactItem:
    return FactItem(fact_type=fact_type, value=value, file=file, line=line, language="Go")


def _build_info(**kwargs) -> BuildInfo:
    return BuildInfo(**kwargs)


# ---------------------------------------------------------------------------
# 1. Port replacement
# ---------------------------------------------------------------------------

class TestPortReplacement:
    def test_replaces_wrong_port_8080_with_real_port(self):
        content = "The server runs on `localhost:8080` by default."
        facts = [_fact("port", "7437")]
        result, corrections = post_process_chapter(content, facts, None, None)
        assert "7437" in result
        assert "8080" not in result
        assert len(corrections) >= 1
        assert any("port" in c.reason.lower() for c in corrections)

    def test_replaces_port_3000(self):
        content = "curl http://localhost:3000/health"
        facts = [_fact("port", "7437")]
        result, corrections = post_process_chapter(content, facts, None, None)
        assert "7437" in result
        assert "3000" not in result

    def test_replaces_engram_port_placeholder(self):
        content = "curl http://localhost:ENGRAM_PORT/api/health"
        facts = [_fact("port", "7437")]
        result, corrections = post_process_chapter(content, facts, None, None)
        assert "localhost:7437/api/health" in result
        assert "ENGRAM_PORT" not in result

    def test_no_replacement_when_port_matches(self):
        content = "The server runs on `localhost:7437` by default."
        facts = [_fact("port", "7437")]
        result, corrections = post_process_chapter(content, facts, None, None)
        assert result == content
        assert len(corrections) == 0

    def test_no_replacement_without_port_facts(self):
        content = "The server runs on `localhost:8080` by default."
        result, corrections = post_process_chapter(content, [], None, None)
        assert "8080" in result
        assert len(corrections) == 0

    def test_replaces_port_5000(self):
        content = "Start the API at :5000\n"
        facts = [_fact("port", "9090")]
        result, corrections = post_process_chapter(content, facts, None, None)
        assert ":9090" in result


# ---------------------------------------------------------------------------
# 2. Version replacement
# ---------------------------------------------------------------------------

class TestVersionReplacement:
    def test_replaces_wrong_go_version(self):
        content = "This project requires Go 1.16 or higher."
        build = _build_info(language="go", go_version="1.23")
        result, corrections = post_process_chapter(content, [], build, None)
        assert "Go 1.23" in result
        assert "Go 1.16" not in result
        assert len(corrections) >= 1

    def test_replaces_go_120_with_real(self):
        content = "Built with Go 1.20.3 toolchain."
        build = _build_info(language="go", go_version="1.25")
        result, corrections = post_process_chapter(content, [], build, None)
        assert "Go 1.25" in result

    def test_no_version_change_when_correct(self):
        content = "Built with Go 1.23 toolchain."
        build = _build_info(language="go", go_version="1.23")
        result, corrections = post_process_chapter(content, [], build, None)
        assert "Go 1.23" in result
        # No corrections for version since it's already correct
        version_corrections = [c for c in corrections if "version" in c.reason.lower() and "Go" in c.reason]
        assert len(version_corrections) == 0

    def test_replaces_project_version(self):
        content = 'The current version is Version "0.1.0".'
        build = _build_info(language="python", version="2.5.0")
        result, corrections = post_process_chapter(content, [], build, None)
        assert "2.5.0" in result

    def test_no_version_replacement_without_build_info(self):
        content = "This requires Go 1.16."
        result, corrections = post_process_chapter(content, [], None, None)
        assert "Go 1.16" in result


# ---------------------------------------------------------------------------
# 3. URL placeholder replacement
# ---------------------------------------------------------------------------

class TestURLPlaceholderReplacement:
    def test_replaces_yourusername(self):
        content = "git clone https://github.com/yourusername/engram.git"
        build = _build_info(module_path="github.com/Gentleman-Programming/engram")
        result, corrections = post_process_chapter(content, [], build, None)
        assert "Gentleman-Programming" in result
        assert "yourusername" not in result

    def test_replaces_your_username_with_dash(self):
        content = "git clone https://github.com/your-username/project.git"
        build = _build_info(module_path="github.com/OrgName/project")
        result, corrections = post_process_chapter(content, [], build, None)
        assert "OrgName" in result
        assert "your-username" not in result

    def test_no_replacement_without_module_path(self):
        content = "git clone https://github.com/yourusername/repo.git"
        build = _build_info(language="go")
        result, corrections = post_process_chapter(content, [], build, None)
        assert "yourusername" in result

    def test_replaces_in_non_clone_url(self):
        content = "Visit https://github.com/yourusername/engram for more."
        build = _build_info(module_path="github.com/Gentleman-Programming/engram")
        result, corrections = post_process_chapter(content, [], build, None)
        assert "Gentleman-Programming" in result


# ---------------------------------------------------------------------------
# 4. Endpoint validation
# ---------------------------------------------------------------------------

class TestEndpointValidation:
    def test_flags_fake_endpoint(self):
        content = "The API provides GET /api/v1/users to list users."
        facts = [_fact("endpoint", "GET /health"), _fact("endpoint", "POST /api/observations")]
        result, corrections = post_process_chapter(content, facts, None, None)
        assert "UNVERIFIED" in result
        assert any("hallucinated" in c.reason.lower() or "not found" in c.reason.lower()
                    for c in corrections)

    def test_does_not_flag_real_endpoint(self):
        content = "Use GET /health to check server status."
        facts = [_fact("endpoint", "/health")]
        result, corrections = post_process_chapter(content, facts, None, None)
        # Should not flag /health as unverified
        endpoint_corrections = [c for c in corrections if "endpoint" in c.reason.lower()]
        assert len(endpoint_corrections) == 0

    def test_no_validation_without_endpoint_facts(self):
        content = "The API provides GET /api/v1/users."
        result, corrections = post_process_chapter(content, [], None, None)
        assert "UNVERIFIED" not in result


# ---------------------------------------------------------------------------
# 5. Missing fact injection
# ---------------------------------------------------------------------------

class TestMissingFactInjection:
    def test_injects_missing_endpoints_in_api_reference(self):
        content = "# API Reference\n\nGET /health returns server status."
        facts = [
            _fact("endpoint", "/health"),
            _fact("endpoint", "POST /api/observations", file="handlers.go", line=42),
        ]
        result, corrections = post_process_chapter(
            content, facts, None, None, chapter_file="06-api-reference.md"
        )
        assert "Additional Endpoints" in result
        assert "/api/observations" in result
        assert "handlers.go" in result

    def test_no_injection_when_all_endpoints_present(self):
        content = "# API\n\n/health endpoint.\n/api/observations endpoint."
        facts = [_fact("endpoint", "/health"), _fact("endpoint", "/api/observations")]
        result, corrections = post_process_chapter(
            content, facts, None, None, chapter_file="06-api-reference.md"
        )
        assert "Additional Endpoints" not in result

    def test_injects_missing_tables_in_data_models(self):
        content = "# Data Models\n\nThe sessions table stores session data."
        facts = [
            _fact("db_table", "sessions"),
            _fact("db_table", "observations", file="store.go", line=55),
        ]
        result, corrections = post_process_chapter(
            content, facts, None, None, chapter_file="05-data-models.md"
        )
        assert "Additional Data Tables" in result
        assert "observations" in result

    def test_no_injection_for_non_api_chapter(self):
        content = "# Overview\n\nThe server has endpoints."
        facts = [_fact("endpoint", "POST /api/observations")]
        result, corrections = post_process_chapter(
            content, facts, None, None, chapter_file="01-overview.md"
        )
        assert "Additional Endpoints" not in result


# ---------------------------------------------------------------------------
# 6. No-op when content is already correct
# ---------------------------------------------------------------------------

class TestNoOp:
    def test_correct_content_returns_unchanged(self):
        content = "The server runs on port 7437.\nUse Go 1.23.\n"
        facts = [_fact("port", "7437")]
        build = _build_info(language="go", go_version="1.23")
        result, corrections = post_process_chapter(content, facts, build, None)
        assert result == content
        assert len(corrections) == 0

    def test_empty_content(self):
        result, corrections = post_process_chapter("", [], None, None)
        assert result == ""
        assert len(corrections) == 0

    def test_no_facts_no_build_info(self):
        content = "Some documentation text."
        result, corrections = post_process_chapter(content, [], None, None)
        assert result == content
        assert len(corrections) == 0
