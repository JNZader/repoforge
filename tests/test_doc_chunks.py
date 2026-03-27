"""
tests/test_doc_chunks.py - Tests for pre-digested documentation chunks.

Tests cover:
- chunk_endpoints: endpoint fact formatting, handler association
- chunk_data_models: table + struct extraction
- chunk_mcp_tools: MCP tool detection
- chunk_cli_commands: CLI command formatting
- chunk_architecture: graph context condensing
- chunk_module_summary: per-module API summary
- Size constraints (max_lines)
- Empty input handling
- Integration: chunks injected into chapter prompts
"""

import pytest

from repoforge.intelligence.ast_extractor import ASTSymbol
from repoforge.facts import FactItem


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def endpoint_facts():
    """Endpoint facts as extracted from a Go project."""
    return [
        FactItem(fact_type="endpoint", value="GET /health", file="server.go", line=42, language="Go"),
        FactItem(fact_type="endpoint", value="POST /api/observations", file="handlers.go", line=88, language="Go"),
        FactItem(fact_type="endpoint", value="GET /api/sessions", file="handlers.go", line=120, language="Go"),
        FactItem(fact_type="port", value="7437", file="server.go", line=15, language="Go"),
    ]


@pytest.fixture
def db_facts():
    """Database table facts."""
    return [
        FactItem(fact_type="db_table", value="sessions", file="store.go", line=120, language="Go"),
        FactItem(fact_type="db_table", value="observations", file="store.go", line=145, language="Go"),
        FactItem(fact_type="db_table", value="topic_keys", file="store.go", line=170, language="Go"),
    ]


@pytest.fixture
def cli_facts():
    """CLI command facts."""
    return [
        FactItem(fact_type="cli_command", value="serve", file="main.go", line=30, language="Go"),
        FactItem(fact_type="cli_command", value="mcp", file="main.go", line=35, language="Go"),
        FactItem(fact_type="env_var", value="ENGRAM_DATA_DIR", file="config.go", line=10, language="Go"),
        FactItem(fact_type="env_var", value="ENGRAM_PORT", file="config.go", line=11, language="Go"),
    ]


@pytest.fixture
def handler_symbols():
    """AST symbols for handler functions."""
    return {
        "handlers.go": [
            ASTSymbol(
                name="HandleCreateObservation", kind="function",
                signature="func HandleCreateObservation(w http.ResponseWriter, r *http.Request)",
                params=["w http.ResponseWriter", "r *http.Request"],
                return_type=None, line=85, file="handlers.go",
            ),
            ASTSymbol(
                name="HandleListSessions", kind="function",
                signature="func HandleListSessions(w http.ResponseWriter, r *http.Request)",
                params=["w http.ResponseWriter", "r *http.Request"],
                return_type=None, line=118, file="handlers.go",
            ),
        ],
        "server.go": [
            ASTSymbol(
                name="New", kind="function",
                signature="func New(store *Store, port int) *Server",
                params=["store *Store", "port int"],
                return_type="*Server", line=40, file="server.go",
            ),
        ],
    }


@pytest.fixture
def model_symbols():
    """AST symbols for data model types."""
    return {
        "types.go": [
            ASTSymbol(
                name="Observation", kind="struct",
                signature="type Observation struct",
                fields=["ID int64", "Content string", "Title string",
                         "Type string", "Project string", "CreatedAt time.Time"],
                line=15, file="types.go",
            ),
            ASTSymbol(
                name="Session", kind="struct",
                signature="type Session struct",
                fields=["ID int64", "Project string", "StartedAt time.Time", "EndedAt *time.Time"],
                line=30, file="types.go",
            ),
        ],
        "store.go": [
            ASTSymbol(
                name="Store", kind="struct",
                signature="type Store struct",
                fields=["db *sql.DB", "dataDir string"],
                line=10, file="store.go",
            ),
        ],
    }


@pytest.fixture
def mcp_symbols():
    """AST symbols from MCP-related files."""
    return {
        "mcp.go": [
            ASTSymbol(
                name="HandleToolCall", kind="function",
                signature="func HandleToolCall(name string, args map[string]interface{}) (string, error)",
                params=["name string", "args map[string]interface{}"],
                return_type="(string, error)", line=50, file="mcp.go",
            ),
            ASTSymbol(
                name="RegisterTools", kind="function",
                signature="func RegisterTools(server *mcp.Server)",
                params=["server *mcp.Server"],
                return_type=None, line=20, file="mcp.go",
            ),
        ],
    }


# ---------------------------------------------------------------------------
# Tests: chunk_endpoints
# ---------------------------------------------------------------------------

class TestChunkEndpoints:
    def test_produces_output_for_endpoint_facts(self, endpoint_facts, handler_symbols):
        from repoforge.intelligence.doc_chunks import chunk_endpoints
        result = chunk_endpoints(endpoint_facts, handler_symbols)
        assert result != ""
        assert "GET /health" in result
        assert "POST /api/observations" in result
        assert "GET /api/sessions" in result

    def test_includes_port_info(self, endpoint_facts, handler_symbols):
        from repoforge.intelligence.doc_chunks import chunk_endpoints
        result = chunk_endpoints(endpoint_facts, handler_symbols)
        assert "7437" in result

    def test_associates_handler_with_endpoint(self, endpoint_facts, handler_symbols):
        from repoforge.intelligence.doc_chunks import chunk_endpoints
        result = chunk_endpoints(endpoint_facts, handler_symbols)
        # HandleCreateObservation is at line 85, endpoint POST /api/observations at line 88
        assert "HandleCreateObservation" in result

    def test_empty_for_no_endpoints(self, handler_symbols):
        from repoforge.intelligence.doc_chunks import chunk_endpoints
        result = chunk_endpoints([], {})
        assert result == ""

    def test_respects_max_lines(self, endpoint_facts, handler_symbols):
        from repoforge.intelligence.doc_chunks import chunk_endpoints
        result = chunk_endpoints(endpoint_facts, handler_symbols, max_lines=5)
        # Non-blank content lines should be constrained
        content_lines = [l for l in result.strip().split("\n") if l.strip()]
        assert content_lines  # at least some output
        # With max_lines=5, we get header + port + a few endpoints (truncated)
        assert len(content_lines) <= 8  # reasonable upper bound with headers

    def test_works_with_no_ast_symbols(self, endpoint_facts):
        from repoforge.intelligence.doc_chunks import chunk_endpoints
        result = chunk_endpoints(endpoint_facts, {})
        assert "GET /health" in result


# ---------------------------------------------------------------------------
# Tests: chunk_data_models
# ---------------------------------------------------------------------------

class TestChunkDataModels:
    def test_produces_output_for_model_symbols(self, db_facts, model_symbols):
        from repoforge.intelligence.doc_chunks import chunk_data_models
        result = chunk_data_models(db_facts, model_symbols)
        assert result != ""
        assert "Observation" in result
        assert "Session" in result

    def test_includes_db_tables(self, db_facts, model_symbols):
        from repoforge.intelligence.doc_chunks import chunk_data_models
        result = chunk_data_models(db_facts, model_symbols)
        assert "sessions" in result
        assert "observations" in result

    def test_includes_struct_fields(self, db_facts, model_symbols):
        from repoforge.intelligence.doc_chunks import chunk_data_models
        result = chunk_data_models(db_facts, model_symbols)
        assert "Content string" in result or "ID int64" in result

    def test_empty_for_no_models(self):
        from repoforge.intelligence.doc_chunks import chunk_data_models
        result = chunk_data_models([], {})
        assert result == ""

    def test_respects_max_lines(self, db_facts, model_symbols):
        from repoforge.intelligence.doc_chunks import chunk_data_models
        # With max_lines=10, output is shorter than with default
        result_short = chunk_data_models(db_facts, model_symbols, max_lines=10)
        result_long = chunk_data_models(db_facts, model_symbols, max_lines=100)
        # Short version should have fewer or equal lines
        short_lines = [l for l in result_short.strip().split("\n") if l.strip()]
        long_lines = [l for l in result_long.strip().split("\n") if l.strip()]
        assert len(short_lines) <= len(long_lines)


# ---------------------------------------------------------------------------
# Tests: chunk_mcp_tools
# ---------------------------------------------------------------------------

class TestChunkMcpTools:
    def test_produces_output_for_mcp_symbols(self, mcp_symbols):
        from repoforge.intelligence.doc_chunks import chunk_mcp_tools
        result = chunk_mcp_tools(mcp_symbols, [])
        assert result != ""
        assert "HandleToolCall" in result or "RegisterTools" in result

    def test_empty_for_no_mcp_files(self, handler_symbols):
        from repoforge.intelligence.doc_chunks import chunk_mcp_tools
        result = chunk_mcp_tools(handler_symbols, [])
        # handler_symbols has "handlers.go" and "server.go" — neither is MCP
        assert result == ""


# ---------------------------------------------------------------------------
# Tests: chunk_cli_commands
# ---------------------------------------------------------------------------

class TestChunkCliCommands:
    def test_produces_output_for_cli_facts(self, cli_facts):
        from repoforge.intelligence.doc_chunks import chunk_cli_commands
        result = chunk_cli_commands(cli_facts, {})
        assert result != ""
        assert "serve" in result
        assert "mcp" in result

    def test_includes_env_vars(self, cli_facts):
        from repoforge.intelligence.doc_chunks import chunk_cli_commands
        result = chunk_cli_commands(cli_facts, {})
        assert "ENGRAM_DATA_DIR" in result

    def test_empty_for_no_commands(self):
        from repoforge.intelligence.doc_chunks import chunk_cli_commands
        result = chunk_cli_commands([], {})
        assert result == ""


# ---------------------------------------------------------------------------
# Tests: chunk_architecture
# ---------------------------------------------------------------------------

class TestChunkArchitecture:
    def test_produces_output_for_graph_context(self):
        from repoforge.intelligence.doc_chunks import chunk_architecture
        graph = "## Dependency Analysis\n**Modules**: 15 | **Dependencies**: 22\n### Most Connected"
        result = chunk_architecture(graph)
        assert result != ""
        assert "Dependency Analysis" in result

    def test_includes_build_info(self):
        from repoforge.intelligence.doc_chunks import chunk_architecture
        result = chunk_architecture("", {"build_tool": "go", "packages": ["internal/store", "cmd/server"]})
        assert "go" in result
        assert "internal/store" in result

    def test_empty_for_no_input(self):
        from repoforge.intelligence.doc_chunks import chunk_architecture
        result = chunk_architecture("")
        assert result == ""


# ---------------------------------------------------------------------------
# Tests: chunk_module_summary
# ---------------------------------------------------------------------------

class TestChunkModuleSummary:
    def test_produces_output(self, handler_symbols):
        from repoforge.intelligence.doc_chunks import chunk_module_summary
        symbols = handler_symbols["handlers.go"]
        result = chunk_module_summary("handlers.go", symbols)
        assert result != ""
        assert "handlers.go" in result
        assert "HandleCreateObservation" in result

    def test_empty_for_no_symbols(self):
        from repoforge.intelligence.doc_chunks import chunk_module_summary
        result = chunk_module_summary("empty.go", [])
        assert result == ""

    def test_includes_struct_fields(self, model_symbols):
        from repoforge.intelligence.doc_chunks import chunk_module_summary
        symbols = model_symbols["types.go"]
        result = chunk_module_summary("types.go", symbols)
        assert "Observation" in result
        assert "Session" in result


# ---------------------------------------------------------------------------
# Tests: Integration — chunks injected into prompts
# ---------------------------------------------------------------------------

class TestChunkPromptIntegration:
    def test_api_reference_includes_endpoint_chunk(self):
        """When doc_chunks has endpoints, api_reference prompt includes them."""
        from repoforge.docs_prompts import get_chapter_prompts
        repo_map = {
            "root": "/fake",
            "tech_stack": ["Go"],
            "entry_points": ["main.go"],
            "config_files": ["go.mod"],
            "layers": {"main": {"path": ".", "modules": [
                {"path": "internal/handler/user_handler.go", "name": "user_handler",
                 "language": "Go", "exports": ["GetUser", "CreateUser"],
                 "imports": ["github"], "summary_hint": "User HTTP handlers"},
            ]}},
            "stats": {"total_files": 12, "by_extension": {".go": 12},
                       "rg_available": False, "rg_version": None},
        }
        chunks = {
            "endpoints": "- `GET /health` (server.go:42)\n- `POST /api/users` (handlers.go:88)",
            "data_models": "",
            "mcp_tools": "",
            "cli_commands": "",
            "architecture": "",
            "module_summaries": "",
        }
        chapters = get_chapter_prompts(repo_map, "English", "TestAPI", doc_chunks=chunks)
        api_ch = next((c for c in chapters if c["file"] == "06-api-reference.md"), None)
        assert api_ch is not None
        assert "GET /health" in api_ch["user"]
        assert "POST /api/users" in api_ch["user"]

    def test_data_models_includes_models_chunk(self):
        """When doc_chunks has data_models, the prompt includes them."""
        from repoforge.docs_prompts import get_chapter_prompts
        repo_map = {
            "root": "/fake",
            "tech_stack": ["Go"],
            "entry_points": ["main.go"],
            "config_files": ["go.mod"],
            "layers": {"main": {"path": ".", "modules": [
                {"path": "internal/handler/user_handler.go", "name": "user_handler",
                 "language": "Go", "exports": ["GetUser"],
                 "imports": ["github"], "summary_hint": "User handlers"},
            ]}},
            "stats": {"total_files": 12, "by_extension": {".go": 12},
                       "rg_available": False, "rg_version": None},
        }
        chunks = {
            "endpoints": "",
            "data_models": "### Type Definitions\n- `type Session struct` { ID int64; Project string }",
            "mcp_tools": "",
            "cli_commands": "",
            "architecture": "",
            "module_summaries": "",
        }
        chapters = get_chapter_prompts(repo_map, "English", "TestModels", doc_chunks=chunks)
        dm_ch = next((c for c in chapters if c["file"] == "05-data-models.md"), None)
        assert dm_ch is not None
        assert "type Session struct" in dm_ch["user"]

    def test_chunks_are_optional(self):
        """Without doc_chunks, prompts still work (backward compat)."""
        from repoforge.docs_prompts import get_chapter_prompts
        repo_map = {
            "root": "/fake",
            "tech_stack": ["Python"],
            "entry_points": ["main.py"],
            "config_files": [],
            "layers": {"main": {"path": ".", "modules": [
                {"path": "main.py", "name": "main", "language": "Python",
                 "exports": ["main"], "imports": [], "summary_hint": "Entry point"},
            ]}},
            "stats": {"total_files": 1, "by_extension": {".py": 1},
                       "rg_available": False, "rg_version": None},
        }
        # No doc_chunks argument
        chapters = get_chapter_prompts(repo_map, "English", "Test")
        assert len(chapters) >= 5
        for ch in chapters:
            assert "system" in ch
            assert "user" in ch

    def test_overview_includes_module_summaries(self):
        """When doc_chunks has module_summaries, overview prompt includes them."""
        from repoforge.docs_prompts import get_chapter_prompts
        repo_map = {
            "root": "/fake",
            "tech_stack": ["Go"],
            "entry_points": ["main.go"],
            "config_files": ["go.mod"],
            "layers": {"main": {"path": ".", "modules": [
                {"path": "server.go", "name": "server",
                 "language": "Go", "exports": ["New", "Start"],
                 "imports": ["net/http"], "summary_hint": "HTTP server"},
            ]}},
            "stats": {"total_files": 5, "by_extension": {".go": 5},
                       "rg_available": False, "rg_version": None},
        }
        chunks = {
            "endpoints": "",
            "data_models": "",
            "mcp_tools": "",
            "cli_commands": "",
            "architecture": "",
            "module_summaries": "### server.go\n- `func New(store *Store, port int) *Server`",
        }
        chapters = get_chapter_prompts(repo_map, "English", "TestOverview", doc_chunks=chunks)
        overview = next(c for c in chapters if c["file"] == "01-overview.md")
        assert "func New" in overview["user"]
