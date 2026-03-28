"""Tests for repoforge.facts — semantic fact extraction."""

import textwrap
from pathlib import Path

import pytest

from repoforge.facts import FactItem, FACT_PATTERNS, extract_facts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(tmp_path: Path, rel: str, content: str) -> Path:
    """Write a file under tmp_path and return its absolute path."""
    fp = tmp_path / rel
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(textwrap.dedent(content))
    return fp


# ---------------------------------------------------------------------------
# FACT_PATTERNS sanity
# ---------------------------------------------------------------------------

class TestFactPatternsCoverage:
    """Verify that FACT_PATTERNS covers the expected fact types."""

    def test_has_all_expected_types(self):
        expected = {
            "endpoint", "port", "version", "db_table", "cli_command", "env_var",
            "mcp_tool", "fts_ddl", "struct_field", "go_version",
        }
        assert expected == set(FACT_PATTERNS.keys())

    def test_endpoint_has_go_patterns(self):
        assert "Go" in FACT_PATTERNS["endpoint"]

    def test_endpoint_has_python_patterns(self):
        assert "Python" in FACT_PATTERNS["endpoint"]

    def test_port_has_universal(self):
        assert "*" in FACT_PATTERNS["port"]

    def test_env_var_has_universal(self):
        assert "*" in FACT_PATTERNS["env_var"]


# ---------------------------------------------------------------------------
# Go endpoint + port extraction
# ---------------------------------------------------------------------------

class TestGoFacts:
    """Extract facts from Go source code."""

    def test_go_endpoints_and_port(self, tmp_path):
        _write(tmp_path, "server.go", """\
            package main

            import "net/http"

            func main() {
                http.HandleFunc("/health", healthHandler)
                http.HandleFunc("/api/v1/users", usersHandler)
                http.ListenAndServe(":7437", nil)
            }
        """)
        facts = extract_facts(str(tmp_path), ["server.go"])

        endpoints = [f for f in facts if f.fact_type == "endpoint"]
        ports = [f for f in facts if f.fact_type == "port"]

        assert len(endpoints) >= 2
        values = {f.value for f in endpoints}
        assert "/health" in values
        assert "/api/v1/users" in values

        assert len(ports) >= 1
        assert any(f.value == "7437" for f in ports)

    def test_go_echo_framework(self, tmp_path):
        _write(tmp_path, "echo.go", """\
            package main

            func routes(e *echo.Echo) {
                e.GET("/ping", pingHandler)
                e.POST("/items", createItem)
            }
        """)
        facts = extract_facts(str(tmp_path), ["echo.go"])
        endpoints = [f for f in facts if f.fact_type == "endpoint"]
        values = {f.value for f in endpoints}
        assert "/ping" in values
        assert "/items" in values


# ---------------------------------------------------------------------------
# Python endpoint + env var extraction
# ---------------------------------------------------------------------------

class TestPythonFacts:
    """Extract facts from Python source code."""

    def test_fastapi_endpoints(self, tmp_path):
        _write(tmp_path, "routes.py", """\
            from fastapi import APIRouter

            router = APIRouter()

            @router.get("/users")
            def list_users():
                pass

            @router.post("/users")
            def create_user():
                pass
        """)
        facts = extract_facts(str(tmp_path), ["routes.py"])
        endpoints = [f for f in facts if f.fact_type == "endpoint"]
        values = {f.value for f in endpoints}
        assert "/users" in values

    def test_django_path(self, tmp_path):
        _write(tmp_path, "urls.py", """\
            from django.urls import path

            urlpatterns = [
                path("api/health/", health_view),
                path("api/users/", user_view),
            ]
        """)
        facts = extract_facts(str(tmp_path), ["urls.py"])
        endpoints = [f for f in facts if f.fact_type == "endpoint"]
        values = {f.value for f in endpoints}
        assert "api/health/" in values

    def test_python_env_vars(self, tmp_path):
        _write(tmp_path, "config.py", """\
            import os

            DB_URL = os.environ.get("DATABASE_URL")
            SECRET = os.getenv("SECRET_KEY")
        """)
        facts = extract_facts(str(tmp_path), ["config.py"])
        env_vars = [f for f in facts if f.fact_type == "env_var"]
        values = {f.value for f in env_vars}
        assert "DATABASE_URL" in values
        assert "SECRET_KEY" in values


# ---------------------------------------------------------------------------
# TypeScript endpoint extraction
# ---------------------------------------------------------------------------

class TestTypeScriptFacts:
    def test_express_routes(self, tmp_path):
        _write(tmp_path, "app.ts", """\
            import express from 'express';
            const app = express();

            app.get("/api/health", (req, res) => res.send("ok"));
            app.post("/api/items", createItem);
        """)
        facts = extract_facts(str(tmp_path), ["app.ts"])
        endpoints = [f for f in facts if f.fact_type == "endpoint"]
        values = {f.value for f in endpoints}
        assert "/api/health" in values
        assert "/api/items" in values


# ---------------------------------------------------------------------------
# Version extraction (universal)
# ---------------------------------------------------------------------------

class TestVersionFacts:
    def test_version_in_go(self, tmp_path):
        _write(tmp_path, "version.go", """\
            package main

            const Version = "1.2.3"
        """)
        facts = extract_facts(str(tmp_path), ["version.go"])
        versions = [f for f in facts if f.fact_type == "version"]
        assert any(f.value == "1.2.3" for f in versions)

    def test_version_in_python(self, tmp_path):
        _write(tmp_path, "setup.py", """\
            version = "0.4.0"
        """)
        facts = extract_facts(str(tmp_path), ["setup.py"])
        versions = [f for f in facts if f.fact_type == "version"]
        assert any(f.value == "0.4.0" for f in versions)


# ---------------------------------------------------------------------------
# DB table / schema extraction
# ---------------------------------------------------------------------------

class TestDbTableFacts:
    def test_create_table(self, tmp_path):
        _write(tmp_path, "schema.py", """\
            CREATE_SQL = '''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL
            );
            CREATE TABLE posts (
                id SERIAL PRIMARY KEY,
                user_id INT REFERENCES users(id)
            );
            '''
        """)
        facts = extract_facts(str(tmp_path), ["schema.py"])
        tables = [f for f in facts if f.fact_type == "db_table"]
        values = {f.value for f in tables}
        assert "users" in values
        assert "posts" in values

    def test_sqlalchemy_tablename(self, tmp_path):
        _write(tmp_path, "models.py", """\
            from sqlalchemy import Column, Integer, String
            from sqlalchemy.ext.declarative import declarative_base

            Base = declarative_base()

            class User(Base):
                __tablename__ = "users"
                id = Column(Integer, primary_key=True)
        """)
        facts = extract_facts(str(tmp_path), ["models.py"])
        tables = [f for f in facts if f.fact_type == "db_table"]
        assert any(f.value == "users" for f in tables)


# ---------------------------------------------------------------------------
# CLI command extraction
# ---------------------------------------------------------------------------

class TestCliCommandFacts:
    def test_go_cobra_command(self, tmp_path):
        _write(tmp_path, "cmd.go", """\
            package cmd

            var rootCmd = &cobra.Command{
                Use: "repoforge",
            }

            var serveCmd = &cobra.Command{
                Use: "serve",
            }
        """)
        facts = extract_facts(str(tmp_path), ["cmd.go"])
        cmds = [f for f in facts if f.fact_type == "cli_command"]
        values = {f.value for f in cmds}
        assert "repoforge" in values
        assert "serve" in values

    def test_python_click_command(self, tmp_path):
        _write(tmp_path, "cli.py", """\
            import click

            @click.command("generate")
            def generate_cmd():
                pass
        """)
        facts = extract_facts(str(tmp_path), ["cli.py"])
        cmds = [f for f in facts if f.fact_type == "cli_command"]
        values = {f.value for f in cmds}
        assert "generate" in values


# ---------------------------------------------------------------------------
# Port extraction (universal)
# ---------------------------------------------------------------------------

class TestPortFacts:
    def test_port_assignment(self, tmp_path):
        _write(tmp_path, "config.py", """\
            PORT = 8080
            port = "3000"
        """)
        facts = extract_facts(str(tmp_path), ["config.py"])
        ports = [f for f in facts if f.fact_type == "port"]
        values = {f.value for f in ports}
        assert "8080" in values
        assert "3000" in values


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_file_list(self, tmp_path):
        facts = extract_facts(str(tmp_path), [])
        assert facts == []

    def test_nonexistent_file(self, tmp_path):
        facts = extract_facts(str(tmp_path), ["does_not_exist.go"])
        assert facts == []

    def test_unsupported_extension(self, tmp_path):
        _write(tmp_path, "readme.md", "# Hello")
        facts = extract_facts(str(tmp_path), ["readme.md"])
        assert facts == []

    def test_deduplication(self, tmp_path):
        _write(tmp_path, "a.go", """\
            package main
            const Version = "1.0.0"
        """)
        _write(tmp_path, "b.go", """\
            package main
            const Version = "1.0.0"
        """)
        facts = extract_facts(str(tmp_path), ["a.go", "b.go"])
        versions = [f for f in facts if f.fact_type == "version"]
        # Same value should be deduplicated
        assert len(versions) == 1

    def test_fact_item_is_frozen(self):
        f = FactItem("endpoint", "/health", "server.go", 10, "Go")
        with pytest.raises(AttributeError):
            f.value = "/new"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# MCP tool registration extraction
# ---------------------------------------------------------------------------

class TestMcpToolFacts:
    """Extract MCP tool registration facts from Go, Python, and TypeScript."""

    def test_go_mcp_new_tool(self, tmp_path):
        _write(tmp_path, "tools.go", """\
            package main

            func setup() {
                mcp.NewTool("search")
                server.AddTool("query", handler)
            }
        """)
        facts = extract_facts(str(tmp_path), ["tools.go"])
        tools = [f for f in facts if f.fact_type == "mcp_tool"]
        values = {f.value for f in tools}
        assert "search" in values
        assert "query" in values

    def test_python_mcp_decorator(self, tmp_path):
        _write(tmp_path, "tools.py", """\
            from mcp import server

            @mcp.tool
            def search_docs(query: str):
                pass
        """)
        facts = extract_facts(str(tmp_path), ["tools.py"])
        tools = [f for f in facts if f.fact_type == "mcp_tool"]
        assert len(tools) >= 1

    def test_python_mcp_tool_init(self, tmp_path):
        _write(tmp_path, "tools.py", """\
            tool = Tool(name="search_index", handler=fn)
        """)
        facts = extract_facts(str(tmp_path), ["tools.py"])
        tools = [f for f in facts if f.fact_type == "mcp_tool"]
        values = {f.value for f in tools}
        assert "search_index" in values

    def test_python_server_add_tool(self, tmp_path):
        _write(tmp_path, "setup.py", """\
            server.add_tool(search_handler)
        """)
        facts = extract_facts(str(tmp_path), ["setup.py"])
        tools = [f for f in facts if f.fact_type == "mcp_tool"]
        assert len(tools) >= 1

    def test_typescript_server_tool(self, tmp_path):
        _write(tmp_path, "tools.ts", """\
            server.tool("search", async (params) => {
                return results;
            });
        """)
        facts = extract_facts(str(tmp_path), ["tools.ts"])
        tools = [f for f in facts if f.fact_type == "mcp_tool"]
        values = {f.value for f in tools}
        assert "search" in values

    def test_typescript_new_mcp_tool(self, tmp_path):
        _write(tmp_path, "tools.ts", """\
            const tool = new McpTool("search");
        """)
        facts = extract_facts(str(tmp_path), ["tools.ts"])
        tools = [f for f in facts if f.fact_type == "mcp_tool"]
        assert len(tools) >= 1

    def test_negative_comment_not_matched(self, tmp_path):
        _write(tmp_path, "main.go", """\
            package main
            // mcp tool comment about something
            mcpToolName = "foo"
        """)
        facts = extract_facts(str(tmp_path), ["main.go"])
        tools = [f for f in facts if f.fact_type == "mcp_tool"]
        assert len(tools) == 0

    def test_negative_variable_name_python(self, tmp_path):
        _write(tmp_path, "config.py", """\
            mcp_tool_name = "search"
        """)
        facts = extract_facts(str(tmp_path), ["config.py"])
        tools = [f for f in facts if f.fact_type == "mcp_tool"]
        assert len(tools) == 0


# ---------------------------------------------------------------------------
# FTS DDL extraction
# ---------------------------------------------------------------------------

class TestFtsDdlFacts:
    """Extract FTS virtual table creation facts."""

    def test_fts5_create(self, tmp_path):
        _write(tmp_path, "schema.py", """\
            SQL = "CREATE VIRTUAL TABLE notes_fts USING fts5(title, body)"
        """)
        facts = extract_facts(str(tmp_path), ["schema.py"])
        fts = [f for f in facts if f.fact_type == "fts_ddl"]
        assert len(fts) >= 1

    def test_fts4_create(self, tmp_path):
        _write(tmp_path, "schema.py", """\
            SQL = "create virtual table search using fts4(name, content)"
        """)
        facts = extract_facts(str(tmp_path), ["schema.py"])
        fts = [f for f in facts if f.fact_type == "fts_ddl"]
        assert len(fts) >= 1

    def test_negative_regular_table(self, tmp_path):
        _write(tmp_path, "schema.py", """\
            SQL = "CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)"
        """)
        facts = extract_facts(str(tmp_path), ["schema.py"])
        fts = [f for f in facts if f.fact_type == "fts_ddl"]
        assert len(fts) == 0


# ---------------------------------------------------------------------------
# Go exported struct field extraction
# ---------------------------------------------------------------------------

class TestStructFieldFacts:
    """Extract Go exported struct fields."""

    def test_exported_fields(self, tmp_path):
        _write(tmp_path, "config.go", """\
            package config

            type ServerConfig struct {
                Name string
                Port int
                Config *Config
            }
        """)
        facts = extract_facts(str(tmp_path), ["config.go"])
        fields = [f for f in facts if f.fact_type == "struct_field"]
        assert len(fields) >= 3

    def test_negative_unexported_field(self, tmp_path):
        _write(tmp_path, "config.go", """\
            package config

            type internal struct {
                name string
                port int
            }
        """)
        facts = extract_facts(str(tmp_path), ["config.go"])
        fields = [f for f in facts if f.fact_type == "struct_field"]
        assert len(fields) == 0

    def test_negative_function_not_field(self, tmp_path):
        _write(tmp_path, "handler.go", """\
            package handler

            func Name() string {
                return "handler"
            }
        """)
        facts = extract_facts(str(tmp_path), ["handler.go"])
        fields = [f for f in facts if f.fact_type == "struct_field"]
        assert len(fields) == 0


# ---------------------------------------------------------------------------
# Go version from go.mod extraction
# ---------------------------------------------------------------------------

class TestGoVersionFacts:
    """Extract Go version from go.mod-style content."""

    def test_go_version_simple(self, tmp_path):
        _write(tmp_path, "go.mod.go", """\
            go 1.22
        """)
        facts = extract_facts(str(tmp_path), ["go.mod.go"])
        gv = [f for f in facts if f.fact_type == "go_version"]
        assert len(gv) >= 1

    def test_go_version_patch(self, tmp_path):
        _write(tmp_path, "go.mod.go", """\
            go 1.23.1
        """)
        facts = extract_facts(str(tmp_path), ["go.mod.go"])
        gv = [f for f in facts if f.fact_type == "go_version"]
        assert len(gv) >= 1

    def test_negative_no_space(self, tmp_path):
        _write(tmp_path, "ref.go", """\
            package main
            // requires go1.22
        """)
        facts = extract_facts(str(tmp_path), ["ref.go"])
        gv = [f for f in facts if f.fact_type == "go_version"]
        assert len(gv) == 0

    def test_negative_golang_prefix(self, tmp_path):
        _write(tmp_path, "docs.go", """\
            package main
            // golang 1.22 is required
        """)
        facts = extract_facts(str(tmp_path), ["docs.go"])
        gv = [f for f in facts if f.fact_type == "go_version"]
        assert len(gv) == 0
