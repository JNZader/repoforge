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

    def test_engram_port_env_var_not_corrupted(self):
        """Regression: ENGRAM_PORT as env var name must NOT be replaced with the port number."""
        content = (
            "export ENGRAM_PORT=8080\n"
            "The server listens on port 8080\n"
            "port := 8080\n"
        )
        facts = [_fact("port", "7437")]
        result, corrections = post_process_chapter(content, facts, None, None)
        # Env var name must survive intact
        assert "ENGRAM_PORT=7437" in result, f"Expected env var value replaced, got: {result}"
        assert "export ENGRAM_PORT=" in result, f"Env var name was corrupted: {result}"
        assert "export 7437" not in result, f"ENGRAM_PORT name was replaced with port number: {result}"
        # Port numbers in other contexts should still be replaced
        assert "port 7437" in result
        assert "port := 7437" in result
        assert "8080" not in result

    def test_engram_port_in_dollar_variable_not_corrupted(self):
        """$ENGRAM_PORT and ${ENGRAM_PORT} should not be touched."""
        content = "curl http://localhost:$ENGRAM_PORT/health\nexport ENGRAM_PORT=3000\n"
        facts = [_fact("port", "7437")]
        result, corrections = post_process_chapter(content, facts, None, None)
        assert "$ENGRAM_PORT" in result
        assert "ENGRAM_PORT=7437" in result

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

    # --- Bare API route detection ---

    def test_flags_bare_api_route_not_in_facts(self):
        """Bare /api/memory route (no HTTP method) should be flagged when not a real endpoint."""
        content = "The system persists data via `/api/memory` and `/api/sync`."
        facts = [
            _fact("endpoint", "GET /observations"),
            _fact("endpoint", "POST /sessions"),
            _fact("endpoint", "GET /sync/status"),
        ]
        result, corrections = post_process_chapter(content, facts, None, None)
        assert "UNVERIFIED ENDPOINT" in result
        ep_corrections = [c for c in corrections if "Endpoint" in c.reason]
        flagged = {c.original for c in ep_corrections}
        assert "/api/memory" in flagged
        assert "/api/sync" in flagged

    def test_does_not_flag_bare_route_matching_fact(self):
        """/api/observations should NOT be flagged when /observations is a real endpoint."""
        content = "Query observations via `/api/observations`."
        facts = [_fact("endpoint", "GET /observations"), _fact("endpoint", "POST /observations")]
        result, corrections = post_process_chapter(content, facts, None, None)
        ep_corrections = [c for c in corrections if "Endpoint" in c.reason]
        assert len(ep_corrections) == 0, f"Should not flag /api/observations: {ep_corrections}"

    def test_does_not_flag_file_paths(self):
        """File paths like /internal/store/store.go must NOT be flagged."""
        content = (
            "See the implementation in `/internal/store/store.go`.\n"
            "The command lives at `/cmd/engram/main.go`.\n"
        )
        facts = [_fact("endpoint", "GET /health")]
        result, corrections = post_process_chapter(content, facts, None, None)
        ep_corrections = [c for c in corrections if "Endpoint" in c.reason]
        assert len(ep_corrections) == 0, f"File paths should not be flagged: {ep_corrections}"

    def test_does_not_flag_directory_paths(self):
        """Directory references like /internal/store/ should NOT be flagged."""
        content = "The storage layer is in `/internal/store/` directory."
        facts = [_fact("endpoint", "GET /health")]
        result, corrections = post_process_chapter(content, facts, None, None)
        ep_corrections = [c for c in corrections if "Endpoint" in c.reason]
        assert len(ep_corrections) == 0

    def test_flags_v1_route_not_in_facts(self):
        """/v1/users should be flagged as an API route when not in facts."""
        content = "The new API exposes `/v1/users` and `/v2/accounts`."
        facts = [_fact("endpoint", "GET /health")]
        result, corrections = post_process_chapter(content, facts, None, None)
        ep_corrections = [c for c in corrections if "Endpoint" in c.reason]
        flagged = {c.original for c in ep_corrections}
        assert "/v1/users" in flagged
        assert "/v2/accounts" in flagged

    def test_endpoint_with_path_params_matches_fact(self):
        """Route with {id} path param should match fact with :id or {id}."""
        content = "End a session via `POST /sessions/{id}/end`."
        facts = [_fact("endpoint", "POST /sessions/:id/end")]
        result, corrections = post_process_chapter(content, facts, None, None)
        ep_corrections = [c for c in corrections if "Endpoint" in c.reason]
        assert len(ep_corrections) == 0

    def test_already_flagged_line_not_double_flagged(self):
        """Lines with existing UNVERIFIED comment should not get a second one."""
        content = (
            "Uses `/api/fake` for data.\n"
            "<!-- UNVERIFIED ENDPOINT: /api/fake not found in extracted endpoints -->"
        )
        facts = [_fact("endpoint", "GET /health")]
        result, corrections = post_process_chapter(content, facts, None, None)
        assert result.count("UNVERIFIED ENDPOINT") == 2  # original + new for first line


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
# 6. Dependency validation
# ---------------------------------------------------------------------------

class TestDependencyValidation:
    """Tests for _fix_dependencies — flags hallucinated external deps."""

    def test_flags_hallucinated_go_dep(self):
        """gorilla/mux NOT in deps should be flagged."""
        content = "The project uses `github.com/gorilla/mux` for HTTP routing."
        build = _build_info(
            language="go",
            dependencies=[
                "modernc.org/sqlite",
                "github.com/charmbracelet/bubbletea",
            ],
        )
        result, corrections = post_process_chapter(content, [], build, None)
        assert "UNVERIFIED DEPENDENCY" in result
        assert any("gorilla/mux" in c.reason for c in corrections)

    def test_does_not_flag_real_go_dep(self):
        """charmbracelet/bubbletea IS in deps — must NOT be flagged."""
        content = "Uses `github.com/charmbracelet/bubbletea` for the TUI."
        build = _build_info(
            language="go",
            dependencies=["github.com/charmbracelet/bubbletea"],
        )
        result, corrections = post_process_chapter(content, [], build, None)
        assert "UNVERIFIED DEPENDENCY" not in result
        dep_corrections = [c for c in corrections if "Dependency" in c.reason]
        assert len(dep_corrections) == 0

    def test_no_changes_without_dep_mentions(self):
        """Content with no dependency-like patterns should pass through."""
        content = "This is a simple overview chapter with no deps mentioned."
        build = _build_info(
            language="go",
            dependencies=["github.com/charmbracelet/bubbletea"],
        )
        result, corrections = post_process_chapter(content, [], build, None)
        assert result == content
        dep_corrections = [c for c in corrections if "Dependency" in c.reason]
        assert len(dep_corrections) == 0

    def test_no_changes_without_build_info(self):
        """No build_info → skip dep validation entirely."""
        content = "Uses github.com/gorilla/mux for routing."
        result, corrections = post_process_chapter(content, [], None, None)
        assert "UNVERIFIED" not in result

    def test_no_changes_with_empty_deps(self):
        """Empty deps list → skip dep validation."""
        content = "Uses github.com/gorilla/mux for routing."
        build = _build_info(language="go", dependencies=[])
        result, corrections = post_process_chapter(content, [], build, None)
        assert "UNVERIFIED DEPENDENCY" not in result

    def test_flags_multiple_fake_deps(self):
        """Multiple hallucinated deps on different lines."""
        content = (
            "Uses `github.com/gorilla/mux` for routing.\n"
            "Configuration via `github.com/spf13/cobra`.\n"
            "Real dep: `github.com/charmbracelet/bubbletea`.\n"
        )
        build = _build_info(
            language="go",
            dependencies=["github.com/charmbracelet/bubbletea"],
        )
        result, corrections = post_process_chapter(content, [], build, None)
        dep_corrections = [c for c in corrections if "Dependency" in c.reason]
        flagged_deps = {c.original for c in dep_corrections}
        assert "github.com/gorilla/mux" in flagged_deps
        assert "github.com/spf13/cobra" in flagged_deps
        assert "github.com/charmbracelet/bubbletea" not in flagged_deps

    def test_does_not_flag_go_stdlib_paths(self):
        """Go stdlib paths like net/http should NOT be flagged."""
        content = "Import `net/http` and `database/sql` for the server."
        build = _build_info(
            language="go",
            dependencies=["github.com/charmbracelet/bubbletea"],
        )
        result, corrections = post_process_chapter(content, [], build, None)
        dep_corrections = [c for c in corrections if "Dependency" in c.reason]
        assert len(dep_corrections) == 0

    def test_subpath_matches_real_dep(self):
        """github.com/org/repo/subpkg should match github.com/org/repo in deps."""
        content = "Uses `github.com/charmbracelet/bubbletea/tea` for the app."
        build = _build_info(
            language="go",
            dependencies=["github.com/charmbracelet/bubbletea"],
        )
        result, corrections = post_process_chapter(content, [], build, None)
        assert "UNVERIFIED DEPENDENCY" not in result

    def test_flags_npm_scoped_package(self):
        """Scoped npm packages not in deps should be flagged."""
        content = "Install `@anthropic-ai/sdk` for the AI features."
        build = _build_info(
            language="typescript",
            dependencies=["express", "zod"],
        )
        result, corrections = post_process_chapter(content, [], build, None)
        assert "UNVERIFIED DEPENDENCY" in result
        assert any("@anthropic-ai/sdk" in c.reason for c in corrections)

    def test_does_not_flag_real_npm_scoped_package(self):
        """Scoped npm package that IS in deps should pass."""
        content = "Uses `@anthropic-ai/sdk` for streaming."
        build = _build_info(
            language="typescript",
            dependencies=["@anthropic-ai/sdk", "express"],
        )
        result, corrections = post_process_chapter(content, [], build, None)
        dep_corrections = [c for c in corrections if "Dependency" in c.reason]
        assert len(dep_corrections) == 0

    def test_flags_pip_install_target(self):
        """pip install of a package not in deps should be flagged."""
        content = "Install with `pip install flask`."
        build = _build_info(
            language="python",
            dependencies=["django", "celery"],
        )
        result, corrections = post_process_chapter(content, [], build, None)
        assert "UNVERIFIED DEPENDENCY" in result
        assert any("flask" in c.reason for c in corrections)

    def test_does_not_flag_real_pip_package(self):
        """pip install of a real dep should pass."""
        content = "Install with `pip install django`."
        build = _build_info(
            language="python",
            dependencies=["django", "celery"],
        )
        result, corrections = post_process_chapter(content, [], build, None)
        dep_corrections = [c for c in corrections if "Dependency" in c.reason]
        assert len(dep_corrections) == 0

    def test_dev_deps_are_not_flagged(self):
        """Dev dependencies should be considered valid too."""
        content = "Uses `github.com/stretchr/testify` for testing."
        build = _build_info(
            language="go",
            dependencies=["github.com/charmbracelet/bubbletea"],
            dev_dependencies=["github.com/stretchr/testify"],
        )
        result, corrections = post_process_chapter(content, [], build, None)
        dep_corrections = [c for c in corrections if "Dependency" in c.reason]
        assert len(dep_corrections) == 0

    def test_already_flagged_line_not_double_flagged(self):
        """Lines already containing UNVERIFIED DEP comment should be skipped."""
        content = (
            "Uses `github.com/gorilla/mux` for routing.\n"
            "<!-- UNVERIFIED DEPENDENCY: github.com/gorilla/mux — not found in project build files -->"
        )
        build = _build_info(
            language="go",
            dependencies=["github.com/charmbracelet/bubbletea"],
        )
        result, corrections = post_process_chapter(content, [], build, None)
        # The comment line itself should not get a second comment appended
        assert result.count("UNVERIFIED DEPENDENCY") == 2  # original + new for first line

    def test_module_path_not_flagged_as_dep(self):
        """The project's own module path should not be flagged."""
        content = "Import from `github.com/Gentleman-Programming/engram/internal`."
        build = _build_info(
            language="go",
            module_path="github.com/Gentleman-Programming/engram",
            dependencies=["modernc.org/sqlite"],
        )
        result, corrections = post_process_chapter(content, [], build, None)
        dep_corrections = [c for c in corrections if "Dependency" in c.reason]
        assert len(dep_corrections) == 0


# ---------------------------------------------------------------------------
# 7. No-op when content is already correct
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
