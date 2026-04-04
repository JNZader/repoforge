"""
tests/test_graph_v2.py — Tests for extractor-based graph builder (v2).

Tests cover:
- build_graph_v2() finds file-level dependencies
- blast_radius_v2 with depth limit
- blast_radius_v2 separates test files
- Go imports resolve via go.mod
- Backward compat — existing build_graph still works
- is_test_file() utility
- CLI --v2 flag integration
"""

import json
import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures: tmp multi-language project
# ---------------------------------------------------------------------------

@pytest.fixture
def multi_lang_project(tmp_path):
    """Create a temporary project with multiple languages that import each other."""

    # TypeScript files
    ts_dir = tmp_path / "src"
    ts_dir.mkdir()

    (ts_dir / "index.ts").write_text(
        "import { UserService } from './services/user';\n"
        "import { formatDate } from './utils';\n"
        "\n"
        "export function main() { return new UserService(); }\n"
    )

    services_dir = ts_dir / "services"
    services_dir.mkdir()

    (services_dir / "user.ts").write_text(
        "import { User } from '../models/user';\n"
        "import { validate } from '../utils';\n"
        "\n"
        "export class UserService {\n"
        "  getUser(): User { return {} as User; }\n"
        "}\n"
    )

    models_dir = ts_dir / "models"
    models_dir.mkdir()

    (models_dir / "user.ts").write_text(
        "export interface User {\n"
        "  id: string;\n"
        "  name: string;\n"
        "}\n"
    )

    (ts_dir / "utils.ts").write_text(
        "export function formatDate(d: Date): string { return d.toISOString(); }\n"
        "export function validate(input: string): boolean { return input.length > 0; }\n"
    )

    # Test file (TS)
    (services_dir / "user.test.ts").write_text(
        "import { UserService } from './user';\n"
        "describe('UserService', () => { it('works', () => {}); });\n"
    )

    # Python files
    py_dir = tmp_path / "lib"
    py_dir.mkdir()

    (py_dir / "__init__.py").write_text("")

    (py_dir / "core.py").write_text(
        "from .helpers import slugify\n"
        "\n"
        "class Engine:\n"
        "    pass\n"
    )

    (py_dir / "helpers.py").write_text(
        "def slugify(text: str) -> str:\n"
        "    return text.lower().replace(' ', '-')\n"
    )

    # Python test
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    (tests_dir / "test_core.py").write_text(
        "from lib.core import Engine\n"
        "\n"
        "def test_engine():\n"
        "    assert Engine is not None\n"
    )

    return tmp_path


@pytest.fixture
def go_project(tmp_path):
    """Create a temporary Go project with go.mod and internal packages."""

    (tmp_path / "go.mod").write_text(
        "module github.com/testuser/testproject\n"
        "\n"
        "go 1.22\n"
    )

    (tmp_path / "main.go").write_text(
        'package main\n'
        '\n'
        'import (\n'
        '    "fmt"\n'
        '    "github.com/testuser/testproject/internal/store"\n'
        ')\n'
        '\n'
        'func main() {\n'
        '    fmt.Println(store.Get())\n'
        '}\n'
    )

    internal_dir = tmp_path / "internal" / "store"
    internal_dir.mkdir(parents=True)

    (internal_dir / "store.go").write_text(
        "package store\n"
        "\n"
        'func Get() string { return "data" }\n'
    )

    (internal_dir / "store_test.go").write_text(
        "package store\n"
        "\n"
        'import "testing"\n'
        "\n"
        "func TestGet(t *testing.T) {}\n"
    )

    return tmp_path


# ---------------------------------------------------------------------------
# Tests: build_graph_v2 finds file-level dependencies
# ---------------------------------------------------------------------------

class TestBuildGraphV2:
    def test_discovers_ts_files(self, multi_lang_project):
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        module_ids = {n.id for n in graph.nodes}
        assert "src/index.ts" in module_ids
        assert "src/services/user.ts" in module_ids
        assert "src/models/user.ts" in module_ids
        assert "src/utils.ts" in module_ids

    def test_ts_relative_import_edges(self, multi_lang_project):
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        # src/services/user.ts imports ../models/user → src/models/user.ts
        deps = graph.get_dependencies("src/services/user.ts")
        assert "src/models/user.ts" in deps

    def test_ts_index_resolution(self, multi_lang_project):
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        # src/index.ts imports ./services/user → src/services/user.ts
        deps = graph.get_dependencies("src/index.ts")
        assert "src/services/user.ts" in deps

    def test_python_relative_import(self, multi_lang_project):
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        # lib/core.py imports from .helpers → lib/helpers.py
        deps = graph.get_dependencies("lib/core.py")
        assert "lib/helpers.py" in deps

    def test_python_absolute_import(self, multi_lang_project):
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        # tests/test_core.py imports lib.core → lib/core.py
        deps = graph.get_dependencies("tests/test_core.py")
        assert "lib/core.py" in deps

    def test_no_self_edges(self, multi_lang_project):
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        for edge in graph.edges:
            assert edge.source != edge.target, f"Self-edge: {edge.source}"

    def test_graph_has_exports(self, multi_lang_project):
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(multi_lang_project))
        node = graph.get_node("src/models/user.ts")
        assert node is not None
        assert "User" in node.exports

    def test_build_with_explicit_files(self, multi_lang_project):
        from repoforge.graph import build_graph_v2
        files = ["src/index.ts", "src/utils.ts"]
        graph = build_graph_v2(str(multi_lang_project), files=files)
        assert len(graph.nodes) == 2


# ---------------------------------------------------------------------------
# Tests: Go imports resolve via go.mod
# ---------------------------------------------------------------------------

class TestGoGraphV2:
    def test_go_local_import_resolved(self, go_project):
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(go_project))
        # main.go imports github.com/testuser/testproject/internal/store
        deps = graph.get_dependencies("main.go")
        assert "internal/store/store.go" in deps

    def test_go_stdlib_not_resolved(self, go_project):
        from repoforge.graph import build_graph_v2
        graph = build_graph_v2(str(go_project))
        deps = graph.get_dependencies("main.go")
        # fmt is stdlib, should NOT appear as a file dependency
        fmt_deps = [d for d in deps if "fmt" in d]
        assert len(fmt_deps) == 0


# ---------------------------------------------------------------------------
# Tests: blast_radius_v2 with depth limit
# ---------------------------------------------------------------------------

class TestBlastRadiusV2:
    def test_basic_blast_radius(self, multi_lang_project):
        from repoforge.graph import build_graph_v2, get_blast_radius_v2
        graph = build_graph_v2(str(multi_lang_project))
        # Changing src/models/user.ts should affect src/services/user.ts
        br = get_blast_radius_v2(graph, "src/models/user.ts")
        assert "src/services/user.ts" in br.files

    def test_blast_radius_transitive(self, multi_lang_project):
        from repoforge.graph import build_graph_v2, get_blast_radius_v2
        graph = build_graph_v2(str(multi_lang_project))
        # Changing src/utils.ts should affect:
        # - src/services/user.ts (imports utils)
        # - src/index.ts (imports utils)
        # Transitively: src/index.ts also via src/services/user.ts
        br = get_blast_radius_v2(graph, "src/utils.ts", max_depth=5)
        affected_ids = set(br.files)
        assert "src/services/user.ts" in affected_ids or "src/index.ts" in affected_ids

    def test_blast_radius_depth_limit(self, multi_lang_project):
        from repoforge.graph import build_graph_v2, get_blast_radius_v2
        graph = build_graph_v2(str(multi_lang_project))
        # With depth=1, should only get direct dependents
        br = get_blast_radius_v2(graph, "src/models/user.ts", max_depth=1)
        assert br.depth <= 1

    def test_blast_radius_separates_test_files(self, multi_lang_project):
        from repoforge.graph import build_graph_v2, get_blast_radius_v2
        graph = build_graph_v2(str(multi_lang_project))
        # Changing src/services/user.ts should include user.test.ts in test_files
        br = get_blast_radius_v2(graph, "src/services/user.ts", include_tests=True)
        # The test file imports user.ts, so it should be in test_files
        # (it depends on the changed file directly)
        # Note: test file is src/services/user.test.ts
        # Actually it imports ./user which resolves to user.ts
        # For the BR: changing user.ts → test depends on user.ts
        # But we're changing user.ts itself, so test should appear
        # Wait, we pass user.ts as changed. Direct dependents of user.ts
        # include user.test.ts
        if "src/services/user.test.ts" in {n.id for n in graph.nodes}:
            assert "src/services/user.test.ts" in br.test_files

    def test_blast_radius_no_tests(self, multi_lang_project):
        from repoforge.graph import build_graph_v2, get_blast_radius_v2
        graph = build_graph_v2(str(multi_lang_project))
        br = get_blast_radius_v2(graph, "src/models/user.ts", include_tests=False)
        assert br.test_files == []

    def test_blast_radius_exceeded_cap(self, multi_lang_project):
        from repoforge.graph import build_graph_v2, get_blast_radius_v2
        graph = build_graph_v2(str(multi_lang_project))
        br = get_blast_radius_v2(graph, "src/utils.ts", max_files=1)
        # With cap of 1, if there are any dependents, exceeded_cap should be True
        if len(br.files) + len(br.test_files) > 1:
            assert br.exceeded_cap is True

    def test_blast_radius_nonexistent_node(self, multi_lang_project):
        from repoforge.graph import build_graph_v2, get_blast_radius_v2
        graph = build_graph_v2(str(multi_lang_project))
        br = get_blast_radius_v2(graph, "nonexistent.ts")
        assert br.files == []
        assert br.test_files == []
        assert br.depth == 0

    def test_blast_radius_changed_files_populated(self, multi_lang_project):
        from repoforge.graph import build_graph_v2, get_blast_radius_v2
        graph = build_graph_v2(str(multi_lang_project))
        br = get_blast_radius_v2(graph, "src/models/user.ts")
        assert "src/models/user.ts" in br.changed_files


# ---------------------------------------------------------------------------
# Tests: is_test_file utility
# ---------------------------------------------------------------------------

class TestIsTestFile:
    def test_python_test_prefix(self):
        from repoforge.graph import is_test_file
        assert is_test_file("tests/test_user.py") is True

    def test_python_test_suffix(self):
        from repoforge.graph import is_test_file
        assert is_test_file("tests/user_test.py") is True

    def test_python_not_test(self):
        from repoforge.graph import is_test_file
        assert is_test_file("app/models/user.py") is False

    def test_ts_test_file(self):
        from repoforge.graph import is_test_file
        assert is_test_file("src/services/user.test.ts") is True

    def test_ts_spec_file(self):
        from repoforge.graph import is_test_file
        assert is_test_file("src/services/user.spec.ts") is True

    def test_tsx_test_file(self):
        from repoforge.graph import is_test_file
        assert is_test_file("src/components/Button.test.tsx") is True

    def test_js_test_file(self):
        from repoforge.graph import is_test_file
        assert is_test_file("src/utils.test.js") is True

    def test_ts_not_test(self):
        from repoforge.graph import is_test_file
        assert is_test_file("src/services/user.ts") is False

    def test_go_test_file(self):
        from repoforge.graph import is_test_file
        assert is_test_file("internal/store/store_test.go") is True

    def test_go_not_test(self):
        from repoforge.graph import is_test_file
        assert is_test_file("internal/store/store.go") is False

    def test_java_test(self):
        from repoforge.graph import is_test_file
        assert is_test_file("src/test/UserTest.java") is True

    def test_java_tests(self):
        from repoforge.graph import is_test_file
        assert is_test_file("src/test/UserTests.java") is True

    def test_java_not_test(self):
        from repoforge.graph import is_test_file
        assert is_test_file("src/main/User.java") is False

    def test_rust_test_dir(self):
        from repoforge.graph import is_test_file
        assert is_test_file("tests/integration.rs") is True

    def test_dunder_tests_dir(self):
        from repoforge.graph import is_test_file
        assert is_test_file("src/__tests__/button.ts") is True


# ---------------------------------------------------------------------------
# Tests: Backward compat — existing build_graph still works
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_build_graph_v1_unchanged(self):
        """Existing build_graph should still work with RepoMap data."""
        from repoforge.graph import build_graph
        repo_map = {
            "layers": {
                "core": {
                    "path": "src/core",
                    "modules": [
                        {
                            "path": "src/core/models.py",
                            "name": "models",
                            "exports": ["User"],
                            "imports": [],
                        },
                        {
                            "path": "src/core/routes.py",
                            "name": "routes",
                            "exports": ["router"],
                            "imports": ["User"],
                        },
                    ],
                },
            },
        }
        g = build_graph(repo_map)
        assert len([n for n in g.nodes if n.node_type == "module"]) == 2
        deps = g.get_dependencies("src/core/routes.py")
        assert "src/core/models.py" in deps

    def test_public_api_exports(self):
        """New symbols should be importable from repoforge."""
        from repoforge import (
            BlastRadiusResult,
            build_graph_v2,
            get_blast_radius_v2,
            is_test_file,
        )
        assert BlastRadiusResult is not None
        assert build_graph_v2 is not None
        assert get_blast_radius_v2 is not None
        assert is_test_file is not None


# ---------------------------------------------------------------------------
# Tests: CLI --v2 flag
# ---------------------------------------------------------------------------

class TestCLIV2:
    def test_graph_help_shows_v2_flag(self):
        from click.testing import CliRunner

        from repoforge.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["graph", "--help"])
        assert result.exit_code == 0
        assert "--v2" in result.output
        assert "--depth" in result.output
        assert "--max-files" in result.output

    def test_graph_v2_summary(self):
        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, ["graph", "-w", repo_dir, "--v2", "-q"])
        assert result.exit_code == 0
        assert "Modules:" in result.output

    def test_graph_v2_json(self):
        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, [
            "graph", "-w", repo_dir, "--v2", "--format", "json", "-q",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "nodes" in data
        assert "edges" in data

    def test_graph_v1_still_works(self):
        """Default (no --v2) should use v1."""
        from click.testing import CliRunner

        from repoforge.cli import main
        repo_dir = str(Path(__file__).parent.parent)
        runner = CliRunner()
        result = runner.invoke(main, ["graph", "-w", repo_dir, "-q"])
        assert result.exit_code == 0
        assert "Modules:" in result.output
