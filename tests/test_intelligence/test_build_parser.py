"""
Tests for repoforge.intelligence.build_parser

Covers: go.mod, package.json, pyproject.toml, Cargo.toml parsing,
internal package discovery, and graceful degradation on missing/malformed files.
"""

import json
import pytest
from pathlib import Path

from repoforge.intelligence.build_parser import (
    BuildInfo,
    parse_build_files,
    _parse_go_mod,
    _parse_package_json,
    _parse_pyproject_toml,
    _parse_cargo_toml,
    _discover_go_packages,
    _discover_python_packages,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_repo(tmp_path):
    """Create a minimal temporary repo root."""
    return tmp_path


@pytest.fixture
def go_mod_repo(tmp_path):
    """Create a Go project with go.mod and internal packages."""
    go_mod = tmp_path / "go.mod"
    go_mod.write_text(
        'module github.com/example/myservice\n'
        '\n'
        'go 1.22.0\n'
        '\n'
        'require (\n'
        '\tgithub.com/gin-gonic/gin v1.9.1\n'
        '\tgithub.com/lib/pq v1.10.9\n'
        '\tgolang.org/x/crypto v0.14.0\n'
        ')\n'
        '\n'
        'require (\n'
        '\tgithub.com/some/indirect v0.1.0 // indirect\n'
        ')\n'
    )

    # Internal packages
    for pkg in ["cmd/server", "internal/auth", "internal/store", "pkg/util"]:
        d = tmp_path / pkg
        d.mkdir(parents=True)
        (d / "main.go" if "cmd" in pkg else d / f"{pkg.split('/')[-1]}.go").write_text(
            f"package {pkg.split('/')[-1]}\n"
        )

    return tmp_path


@pytest.fixture
def engram_go_mod():
    """Path to the real engram go.mod fixture."""
    p = Path("/tmp/engram-test/go.mod")
    if p.exists():
        return p
    pytest.skip("engram-test fixture not available at /tmp/engram-test/go.mod")


@pytest.fixture
def package_json_repo(tmp_path):
    """Create a Node.js/TypeScript project with package.json."""
    pkg = {
        "name": "@example/web-app",
        "version": "1.2.3",
        "main": "dist/index.js",
        "bin": {"myapp": "./bin/cli.js"},
        "scripts": {
            "dev": "vite",
            "build": "tsc && vite build",
            "test": "vitest",
        },
        "dependencies": {
            "react": "^19.0.0",
            "react-dom": "^19.0.0",
            "zustand": "^5.0.0",
        },
        "devDependencies": {
            "typescript": "^5.5.0",
            "vite": "^6.0.0",
            "vitest": "^2.0.0",
        },
    }
    (tmp_path / "package.json").write_text(json.dumps(pkg, indent=2))
    (tmp_path / "tsconfig.json").write_text("{}")

    # Source dirs
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.ts").write_text("export const main = () => {}")

    return tmp_path


@pytest.fixture
def workspace_repo(tmp_path):
    """Create a monorepo with npm workspaces."""
    pkg = {
        "name": "@example/monorepo",
        "version": "0.0.0",
        "private": True,
        "workspaces": ["packages/*"],
    }
    (tmp_path / "package.json").write_text(json.dumps(pkg, indent=2))

    for name in ["core", "ui", "utils"]:
        d = tmp_path / "packages" / name
        d.mkdir(parents=True)
        (d / "package.json").write_text(json.dumps({"name": f"@example/{name}"}))

    return tmp_path


@pytest.fixture
def pyproject_repo(tmp_path):
    """Create a Python project with pyproject.toml."""
    content = '''\
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "my-cool-lib"
version = "0.5.0"
dependencies = [
    "click>=8.1.0",
    "pyyaml>=6.0",
    "requests>=2.28",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "ruff",
]

[project.scripts]
mycli = "my_cool_lib.cli:main"
'''
    (tmp_path / "pyproject.toml").write_text(content)

    # Python packages
    lib = tmp_path / "my_cool_lib"
    lib.mkdir()
    (lib / "__init__.py").write_text("")
    (lib / "cli.py").write_text("def main(): pass")

    sub = lib / "utils"
    sub.mkdir()
    (sub / "__init__.py").write_text("")

    return tmp_path


@pytest.fixture
def cargo_repo(tmp_path):
    """Create a Rust project with Cargo.toml."""
    content = '''\
[package]
name = "my-rust-app"
version = "0.3.1"

[dependencies]
serde = "1.0"
tokio = { version = "1.0", features = ["full"] }

[dev-dependencies]
assert_cmd = "2.0"
'''
    (tmp_path / "Cargo.toml").write_text(content)
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.rs").write_text("fn main() {}")
    (src / "lib.rs").write_text("pub mod util;")
    util = src / "util"
    util.mkdir()
    (util / "mod.rs").write_text("pub fn helper() {}")

    return tmp_path


@pytest.fixture
def cargo_workspace_repo(tmp_path):
    """Create a Rust workspace with members."""
    content = '''\
[workspace]
members = [
    "crates/*",
]
'''
    (tmp_path / "Cargo.toml").write_text(content)
    for name in ["core", "cli"]:
        d = tmp_path / "crates" / name
        d.mkdir(parents=True)
        (d / "Cargo.toml").write_text(f'[package]\nname = "{name}"\nversion = "0.1.0"\n')
        src = d / "src"
        src.mkdir()
        (src / "lib.rs").write_text("")

    return tmp_path


# ---------------------------------------------------------------------------
# Tests: go.mod
# ---------------------------------------------------------------------------

class TestGoModParsing:

    def test_basic_go_mod(self, go_mod_repo):
        info = parse_build_files(str(go_mod_repo))
        assert info.language == "go"
        assert info.module_path == "github.com/example/myservice"
        assert info.go_version == "1.22.0"

    def test_go_dependencies(self, go_mod_repo):
        info = parse_build_files(str(go_mod_repo))
        assert "github.com/gin-gonic/gin" in info.dependencies
        assert "github.com/lib/pq" in info.dependencies
        assert "golang.org/x/crypto" in info.dependencies
        # Indirect deps should NOT be in direct dependencies
        assert "github.com/some/indirect" not in info.dependencies

    def test_go_package_discovery(self, go_mod_repo):
        info = parse_build_files(str(go_mod_repo))
        assert "cmd/server" in info.packages
        assert "internal/auth" in info.packages
        assert "internal/store" in info.packages
        assert "pkg/util" in info.packages

    def test_go_entry_points(self, go_mod_repo):
        info = parse_build_files(str(go_mod_repo))
        assert "cmd/server" in info.entry_points

    def test_real_engram_go_mod(self, engram_go_mod):
        """Test with the real engram go.mod fixture."""
        root = engram_go_mod.parent
        info = _parse_go_mod(engram_go_mod, root)
        assert info.language == "go"
        assert info.module_path == "github.com/Gentleman-Programming/engram"
        assert info.go_version is not None
        assert "github.com/charmbracelet/bubbletea" in info.dependencies
        assert "github.com/lib/pq" in info.dependencies
        # Should discover internal packages
        assert len(info.packages) > 0

    def test_engram_internal_packages(self, engram_go_mod):
        """Verify internal package discovery on the engram fixture."""
        root = engram_go_mod.parent
        info = _parse_go_mod(engram_go_mod, root)
        # engram has internal/store, internal/tui, cmd/engram, etc.
        pkg_names = [p.split("/")[-1] for p in info.packages]
        # At minimum, some known directories should be found
        assert any("internal" in p for p in info.packages), (
            f"Expected internal packages, found: {info.packages}"
        )


# ---------------------------------------------------------------------------
# Tests: package.json
# ---------------------------------------------------------------------------

class TestPackageJsonParsing:

    def test_basic_package_json(self, package_json_repo):
        info = parse_build_files(str(package_json_repo))
        assert info.language == "typescript"
        assert info.module_path == "@example/web-app"
        assert info.version == "1.2.3"

    def test_dependencies(self, package_json_repo):
        info = parse_build_files(str(package_json_repo))
        assert "react" in info.dependencies
        assert "zustand" in info.dependencies
        assert "typescript" in info.dev_dependencies
        assert "vite" in info.dev_dependencies

    def test_scripts(self, package_json_repo):
        info = parse_build_files(str(package_json_repo))
        assert info.scripts["dev"] == "vite"
        assert info.scripts["build"] == "tsc && vite build"

    def test_entry_points(self, package_json_repo):
        info = parse_build_files(str(package_json_repo))
        assert "dist/index.js" in info.entry_points
        assert "./bin/cli.js" in info.entry_points

    def test_workspace_discovery(self, workspace_repo):
        info = parse_build_files(str(workspace_repo))
        assert "packages/core" in info.packages
        assert "packages/ui" in info.packages
        assert "packages/utils" in info.packages

    def test_js_detection(self, tmp_path):
        """Without typescript dep or tsconfig, should detect as javascript."""
        pkg = {"name": "js-app", "version": "1.0.0", "dependencies": {"express": "^4.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        info = parse_build_files(str(tmp_path))
        assert info.language == "javascript"

    def test_real_repoforge_web(self):
        """Test with the real repoforge apps/web/package.json."""
        web_dir = Path("/home/javier/programacion/repoforge/apps/web")
        if not (web_dir / "package.json").exists():
            pytest.skip("apps/web/package.json not available")
        info = _parse_package_json(web_dir / "package.json", web_dir)
        assert info.language == "typescript"
        assert info.module_path == "@repoforge/web"
        assert "react" in info.dependencies


# ---------------------------------------------------------------------------
# Tests: pyproject.toml
# ---------------------------------------------------------------------------

class TestPyprojectTomlParsing:

    def test_basic_pyproject(self, pyproject_repo):
        info = parse_build_files(str(pyproject_repo))
        assert info.language == "python"
        assert info.module_path == "my-cool-lib"
        assert info.version == "0.5.0"

    def test_python_dependencies(self, pyproject_repo):
        info = parse_build_files(str(pyproject_repo))
        assert "click" in info.dependencies
        assert "pyyaml" in info.dependencies
        assert "requests" in info.dependencies

    def test_python_packages(self, pyproject_repo):
        info = parse_build_files(str(pyproject_repo))
        assert "my_cool_lib" in info.packages
        assert "my_cool_lib/utils" in info.packages

    def test_python_entry_points(self, pyproject_repo):
        info = parse_build_files(str(pyproject_repo))
        # Should find the cli.py entry point
        assert any("cli" in ep for ep in info.entry_points) or "mycli" in info.scripts

    def test_real_repoforge_pyproject(self):
        """Test with the real repoforge pyproject.toml."""
        root = Path("/home/javier/programacion/repoforge")
        if not (root / "pyproject.toml").exists():
            pytest.skip("pyproject.toml not available")
        info = _parse_pyproject_toml(root / "pyproject.toml", root)
        assert info.language == "python"
        assert info.module_path == "repoforge-ai"
        assert info.version is not None
        assert "litellm" in info.dependencies or "click" in info.dependencies
        # Should find repoforge package
        assert any("repoforge" in p for p in info.packages)


# ---------------------------------------------------------------------------
# Tests: Cargo.toml
# ---------------------------------------------------------------------------

class TestCargoTomlParsing:

    def test_basic_cargo(self, cargo_repo):
        info = parse_build_files(str(cargo_repo))
        assert info.language == "rust"
        assert info.module_path == "my-rust-app"
        assert info.version == "0.3.1"

    def test_rust_dependencies(self, cargo_repo):
        info = parse_build_files(str(cargo_repo))
        assert "serde" in info.dependencies
        assert "tokio" in info.dependencies
        assert "assert_cmd" in info.dev_dependencies

    def test_rust_entry_point(self, cargo_repo):
        info = parse_build_files(str(cargo_repo))
        assert "src/main.rs" in info.entry_points

    def test_workspace_members(self, cargo_workspace_repo):
        info = parse_build_files(str(cargo_workspace_repo))
        assert "crates/core" in info.packages
        assert "crates/cli" in info.packages


# ---------------------------------------------------------------------------
# Tests: Graceful degradation
# ---------------------------------------------------------------------------

class TestGracefulDegradation:

    def test_no_manifest_files(self, tmp_repo):
        """Should return empty BuildInfo, not crash."""
        info = parse_build_files(str(tmp_repo))
        assert info.language == ""
        assert info.packages == []
        assert info.dependencies == []

    def test_malformed_go_mod(self, tmp_repo):
        """Malformed go.mod should not crash."""
        (tmp_repo / "go.mod").write_text("this is not valid go.mod content\n!!!")
        info = parse_build_files(str(tmp_repo))
        # Should still return Go language since the file exists,
        # but module_path may be None
        assert info.language == "go"
        assert info.module_path is None

    def test_malformed_package_json(self, tmp_repo):
        """Malformed JSON should gracefully fail."""
        (tmp_repo / "package.json").write_text("{invalid json")
        info = parse_build_files(str(tmp_repo))
        # parse_build_files catches exceptions and moves on
        assert info.language == ""  # fallback to empty

    def test_empty_pyproject(self, tmp_repo):
        """Empty pyproject.toml should not crash."""
        (tmp_repo / "pyproject.toml").write_text("")
        info = parse_build_files(str(tmp_repo))
        assert info.language == "python"

    def test_nonexistent_directory(self):
        """Nonexistent directory should return empty BuildInfo."""
        info = parse_build_files("/nonexistent/path/12345")
        assert info.language == ""


# ---------------------------------------------------------------------------
# Tests: Scanner integration with build parsing
# ---------------------------------------------------------------------------

class TestScannerBuildIntegration:

    def test_scanner_uses_build_info(self, go_mod_repo):
        """Verify scanner discovers more modules when build parsing is active."""
        from repoforge.scanner import scan_repo

        repo_map = scan_repo(str(go_mod_repo))

        # Build info should be present
        assert "build_info" in repo_map
        assert repo_map["build_info"]["language"] == "go"
        assert repo_map["build_info"]["module_path"] == "github.com/example/myservice"
        assert repo_map["build_info"]["go_version"] == "1.22.0"

    def test_scanner_max_files_configurable(self, pyproject_repo):
        """Verify max_files_per_layer parameter works."""
        from repoforge.scanner import scan_repo

        # With a very small cap
        repo_map = scan_repo(str(pyproject_repo), max_files_per_layer=2)
        # Should still work, just with fewer files
        assert "layers" in repo_map

    def test_scanner_entry_points_from_build(self, go_mod_repo):
        """Build-discovered entry points should appear in repo_map."""
        from repoforge.scanner import scan_repo

        repo_map = scan_repo(str(go_mod_repo))
        assert "cmd/server" in repo_map["entry_points"]

    def test_scanner_tech_stack_enriched(self, go_mod_repo):
        """Build info should enrich tech stack detection."""
        from repoforge.scanner import scan_repo

        repo_map = scan_repo(str(go_mod_repo))
        assert "Go" in repo_map["tech_stack"]

    def test_default_max_files_is_500(self):
        """Verify the default changed from 80 to 500."""
        from repoforge.scanner import DEFAULT_MAX_FILES_PER_LAYER
        assert DEFAULT_MAX_FILES_PER_LAYER == 500
