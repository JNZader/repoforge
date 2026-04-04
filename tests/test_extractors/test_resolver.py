"""
tests/test_extractors/test_resolver.py — Tests for import path resolution.

Tests cover:
- Relative TS/JS import resolution with extension probing
- Index file resolution (directory imports)
- .js → .ts cross-resolution
- Go import resolution via go.mod module path
- Python relative import resolution (dot notation)
- Python absolute internal import resolution
- External/unknown imports return None
- Edge cases: empty files set, non-relative imports
"""

import pytest

from repoforge.extractors.resolver import (
    resolve_go_import,
    resolve_import,
    resolve_python_import,
)

# ---------------------------------------------------------------------------
# Fixtures: available file sets
# ---------------------------------------------------------------------------

TS_PROJECT_FILES = {
    "src/api/routes.ts",
    "src/api/utils.ts",
    "src/api/utils.test.ts",
    "src/core/models.ts",
    "src/core/index.ts",
    "src/shared/helpers.tsx",
    "src/shared/types.ts",
    "src/lib/auth.js",
}

PYTHON_PROJECT_FILES = {
    "app/__init__.py",
    "app/models/__init__.py",
    "app/models/user.py",
    "app/models/post.py",
    "app/services/__init__.py",
    "app/services/user_service.py",
    "app/services/auth.py",
    "app/utils.py",
    "tests/test_user.py",
}

GO_PROJECT_FILES = {
    "cmd/main.go",
    "internal/store/store.go",
    "internal/store/store_test.go",
    "internal/auth/auth.go",
    "internal/auth/middleware.go",
    "pkg/utils/helpers.go",
}

GO_MOD_CONTENT = """\
module github.com/user/myproject

go 1.22

require (
    github.com/gorilla/mux v1.8.0
)
"""

RUST_PROJECT_FILES = {
    "src/main.rs",
    "src/lib.rs",
    "src/utils/mod.rs",
    "src/utils/helpers.rs",
}


# ---------------------------------------------------------------------------
# Tests: Relative TS/JS import resolution
# ---------------------------------------------------------------------------

class TestTSJSResolution:
    def test_resolve_relative_same_dir(self):
        result = resolve_import(
            "src/api/routes.ts", "./utils", TS_PROJECT_FILES,
            is_relative=True,
        )
        assert result == "src/api/utils.ts"

    def test_resolve_relative_parent_dir(self):
        result = resolve_import(
            "src/api/routes.ts", "../core/models", TS_PROJECT_FILES,
            is_relative=True,
        )
        assert result == "src/core/models.ts"

    def test_resolve_relative_tsx_extension(self):
        result = resolve_import(
            "src/api/routes.ts", "../shared/helpers", TS_PROJECT_FILES,
            is_relative=True,
        )
        assert result == "src/shared/helpers.tsx"

    def test_resolve_index_file(self):
        """Import of a directory should resolve to index.ts."""
        result = resolve_import(
            "src/api/routes.ts", "../core", TS_PROJECT_FILES,
            is_relative=True,
        )
        assert result == "src/core/index.ts"

    def test_resolve_js_to_ts_cross(self):
        """Import with .js extension should resolve to .ts file."""
        files = {"src/utils.ts", "src/main.ts"}
        result = resolve_import(
            "src/main.ts", "./utils.js", files,
            is_relative=True,
        )
        assert result == "src/utils.ts"

    def test_resolve_exact_match(self):
        """Exact file path match should work."""
        result = resolve_import(
            "src/api/routes.ts", "../lib/auth.js", TS_PROJECT_FILES,
            is_relative=True,
        )
        assert result == "src/lib/auth.js"

    def test_non_relative_returns_none(self):
        """Non-relative imports (external packages) return None."""
        result = resolve_import(
            "src/api/routes.ts", "lodash", TS_PROJECT_FILES,
            is_relative=False,
        )
        assert result is None

    def test_unresolvable_import(self):
        """Import that doesn't match any file returns None."""
        result = resolve_import(
            "src/api/routes.ts", "./nonexistent", TS_PROJECT_FILES,
            is_relative=True,
        )
        assert result is None

    def test_empty_available_files(self):
        result = resolve_import(
            "src/api/routes.ts", "./utils", set(),
            is_relative=True,
        )
        assert result is None


# ---------------------------------------------------------------------------
# Tests: Go import resolution via go.mod
# ---------------------------------------------------------------------------

class TestGoResolution:
    def test_resolve_local_package(self):
        result = resolve_go_import(
            "github.com/user/myproject/internal/store",
            GO_MOD_CONTENT,
            GO_PROJECT_FILES,
        )
        assert result == "internal/store/store.go"

    def test_resolve_local_auth_package(self):
        result = resolve_go_import(
            "github.com/user/myproject/internal/auth",
            GO_MOD_CONTENT,
            GO_PROJECT_FILES,
        )
        # Should return one of the .go files in internal/auth/
        assert result is not None
        assert result.startswith("internal/auth/")
        assert result.endswith(".go")
        assert not result.endswith("_test.go")

    def test_external_package_returns_none(self):
        result = resolve_go_import(
            "github.com/gorilla/mux",
            GO_MOD_CONTENT,
            GO_PROJECT_FILES,
        )
        assert result is None

    def test_stdlib_returns_none(self):
        result = resolve_go_import(
            "fmt",
            GO_MOD_CONTENT,
            GO_PROJECT_FILES,
        )
        assert result is None

    def test_invalid_go_mod(self):
        result = resolve_go_import(
            "github.com/user/myproject/internal/store",
            "this is not a go.mod",
            GO_PROJECT_FILES,
        )
        assert result is None

    def test_module_root_import_returns_none(self):
        """Importing the module root itself returns None."""
        result = resolve_go_import(
            "github.com/user/myproject",
            GO_MOD_CONTENT,
            GO_PROJECT_FILES,
        )
        assert result is None

    def test_skips_test_files(self):
        """Go resolver should not resolve to _test.go files."""
        files = {"internal/store/store_test.go"}
        result = resolve_go_import(
            "github.com/user/myproject/internal/store",
            GO_MOD_CONTENT,
            files,
        )
        assert result is None


# ---------------------------------------------------------------------------
# Tests: Python relative import resolution
# ---------------------------------------------------------------------------

class TestPythonResolution:
    def test_relative_same_package(self):
        """from .user import User → look in same directory."""
        result = resolve_python_import(
            "app/models/post.py", ".user", PYTHON_PROJECT_FILES,
            is_relative=True,
        )
        assert result == "app/models/user.py"

    def test_relative_parent_package(self):
        """from ..utils import foo → go up one directory."""
        result = resolve_python_import(
            "app/services/user_service.py", "..utils", PYTHON_PROJECT_FILES,
            is_relative=True,
        )
        assert result == "app/utils.py"

    def test_relative_single_dot_init(self):
        """from . import models → look for __init__.py in same dir."""
        result = resolve_python_import(
            "app/models/user.py", ".", PYTHON_PROJECT_FILES,
            is_relative=True,
        )
        assert result == "app/models/__init__.py"

    def test_relative_double_dot(self):
        """from .. import something → go to parent package."""
        result = resolve_python_import(
            "app/services/user_service.py", "..", PYTHON_PROJECT_FILES,
            is_relative=True,
        )
        assert result == "app/__init__.py"

    def test_absolute_internal(self):
        """Absolute import that matches internal package."""
        result = resolve_python_import(
            "tests/test_user.py", "app.models.user", PYTHON_PROJECT_FILES,
            is_relative=False,
        )
        assert result == "app/models/user.py"

    def test_absolute_package_init(self):
        """Absolute import of a package resolves to __init__.py."""
        result = resolve_python_import(
            "tests/test_user.py", "app.models", PYTHON_PROJECT_FILES,
            is_relative=False,
        )
        assert result == "app/models/__init__.py"

    def test_external_package_returns_none(self):
        """External packages that don't match any file return None."""
        result = resolve_python_import(
            "app/services/auth.py", "fastapi", PYTHON_PROJECT_FILES,
            is_relative=False,
        )
        assert result is None

    def test_relative_unresolvable(self):
        result = resolve_python_import(
            "app/services/auth.py", ".nonexistent", PYTHON_PROJECT_FILES,
            is_relative=True,
        )
        assert result is None


# ---------------------------------------------------------------------------
# Tests: Rust module resolution
# ---------------------------------------------------------------------------

class TestRustResolution:
    def test_resolve_mod_rs(self):
        """Import of a directory should resolve to mod.rs."""
        result = resolve_import(
            "src/main.rs", "./utils", RUST_PROJECT_FILES,
            is_relative=True,
        )
        assert result == "src/utils/mod.rs"


# ---------------------------------------------------------------------------
# Tests: Edge cases
# ---------------------------------------------------------------------------

class TestResolverEdgeCases:
    def test_source_starts_with_dot_detected_as_relative(self):
        """Source starting with . should resolve even if is_relative=False.

        The resolver checks the actual source string for leading dots,
        so ./utils is always treated as relative regardless of the flag.
        """
        result = resolve_import(
            "src/api/routes.ts", "./utils", TS_PROJECT_FILES,
            is_relative=False,  # Not marked, but source starts with .
        )
        # The resolver detects the leading . and resolves it anyway
        assert result == "src/api/utils.ts"

    def test_deeply_nested_relative(self):
        """Going up 3 dirs from a/b/c/ lands at root, so ./x resolves to x.ts."""
        files = {"a/b/c/d.ts", "x.ts"}
        result = resolve_import(
            "a/b/c/d.ts", "../../../x", files,
            is_relative=True,
        )
        assert result == "x.ts"

    def test_relative_two_levels_up(self):
        """Going up 2 dirs from a/b/c/ lands at a/, so ../x resolves to a/x.ts."""
        files = {"a/b/c/d.ts", "a/x.ts"}
        result = resolve_import(
            "a/b/c/d.ts", "../../x", files,
            is_relative=True,
        )
        assert result == "a/x.ts"
