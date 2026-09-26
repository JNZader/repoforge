"""
Import Resolver

Resolves import specifiers to actual file paths within a project.
Handles relative imports, extension resolution, index files,
Go module paths, and Python relative dot notation.

Ported from ghagga's resolveImportPath() in builder.ts.
"""

import os
from pathlib import PurePosixPath

# ---------------------------------------------------------------------------
# Extension resolution order
# ---------------------------------------------------------------------------

_TS_JS_EXTENSIONS = [".ts", ".tsx", ".js", ".jsx", ".mjs"]
_PYTHON_EXTENSIONS = [".py"]
_GO_EXTENSIONS = [".go"]
_JAVA_EXTENSIONS = [".java"]
_RUST_EXTENSIONS = [".rs"]

_ALL_EXTENSIONS = (
    _TS_JS_EXTENSIONS + _PYTHON_EXTENSIONS + _GO_EXTENSIONS + _JAVA_EXTENSIONS + _RUST_EXTENSIONS
)

# Index files to try when import resolves to a directory.
# Kept for callers that do not identify a language. Language-scoped
# resolution uses _INDEX_BY_FAMILY instead.
_INDEX_FILES = [
    "index.ts",
    "index.tsx",
    "index.js",
    "index.jsx",
    "__init__.py",
    "mod.rs",
]

_TS_JS_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}


def _resolution_family(importer_path: str) -> tuple[list[str], list[str]]:
    """Extensions and index files legal for the importer's language.

    Unknown suffixes keep the historical cross-language search so a caller
    that does not pass a real source path still resolves something.
    """
    suffix = PurePosixPath(importer_path).suffix.lower()
    if suffix in _TS_JS_SUFFIXES:
        return (
            _TS_JS_EXTENSIONS,
            ["index.ts", "index.tsx", "index.js", "index.jsx"],
        )
    if suffix == ".py":
        return _PYTHON_EXTENSIONS, ["__init__.py"]
    if suffix == ".go":
        return _GO_EXTENSIONS, []
    if suffix == ".java":
        return _JAVA_EXTENSIONS, []
    if suffix == ".rs":
        return _RUST_EXTENSIONS, ["mod.rs"]
    return list(_ALL_EXTENSIONS), list(_INDEX_FILES)


# ---------------------------------------------------------------------------
# Main resolver
# ---------------------------------------------------------------------------


def resolve_import(
    importer_path: str,
    import_source: str,
    available_files: set[str],
    root_dir: str = "",
    *,
    is_relative: bool = False,
) -> str | None:
    """Resolve an import specifier to an actual file path.

    Args:
        importer_path: Relative path of the file doing the import
            (e.g., "src/api/routes.ts").
        import_source: The raw import specifier
            (e.g., "./utils", "../core", "lodash").
        available_files: Set of all known project-relative file paths.
        root_dir: Project root directory (used for Go module resolution).
        is_relative: Whether this import is relative (starts with . or ..).

    Returns:
        The resolved project-relative file path, or None if unresolvable.
    """
    # Non-relative imports cannot be resolved to local files
    # (except Go module paths — handled by resolve_go_import)
    if not is_relative and not import_source.startswith("."):
        return None

    # Compute the absolute resolved path from importer dir + relative import
    importer_dir = str(PurePosixPath(importer_path).parent)
    resolved = str(PurePosixPath(os.path.normpath(PurePosixPath(importer_dir) / import_source)))

    # Normalize: remove leading ./
    if resolved.startswith("./"):
        resolved = resolved[2:]

    extensions, index_files = _resolution_family(importer_path)

    # 1. Exact match
    if resolved in available_files:
        return resolved

    # 2. Try with extensions of the importer's language
    for ext in extensions:
        candidate = f"{resolved}{ext}"
        if candidate in available_files:
            return candidate

    # 3. Try index files (directory imports)
    for index_file in index_files:
        candidate = f"{resolved}/{index_file}"
        if candidate in available_files:
            return candidate

    # 4. .js → .ts cross-resolution (TypeScript projects often use .js in imports)
    if resolved.endswith(".js") and PurePosixPath(importer_path).suffix.lower() in _TS_JS_SUFFIXES:
        ts_path = resolved[:-3] + ".ts"
        if ts_path in available_files:
            return ts_path
        tsx_path = resolved[:-3] + ".tsx"
        if tsx_path in available_files:
            return tsx_path

    return None


# ---------------------------------------------------------------------------
# Go-specific resolver
# ---------------------------------------------------------------------------


def resolve_go_import(
    import_path: str,
    go_mod_path: str,
    available_files: set[str],
    root_dir: str = "",
) -> str | None:
    """Resolve a Go import path to a local file using go.mod module path.

    Go doesn't use relative imports — it uses full module paths like
    "github.com/user/repo/internal/store". We strip the module prefix
    from go.mod and map to local directories.

    Args:
        import_path: The Go import path (e.g., "github.com/user/repo/pkg/auth").
        go_mod_path: Path to go.mod file content (the module line will be parsed).
        available_files: Set of all known project-relative file paths.
        root_dir: Project root directory.

    Returns:
        The resolved project-relative file path (directory), or None.
    """
    module_path = _parse_go_module(go_mod_path)
    if not module_path:
        return None

    # Check if import starts with the module path
    if not import_path.startswith(module_path):
        return None  # External dependency

    # Strip module prefix to get relative path
    relative = import_path[len(module_path) :].lstrip("/")
    if not relative:
        return None  # Importing the module root itself

    # In Go, imports point to packages (directories), not files.
    # Look for any .go file in that directory.
    for file_path in available_files:
        if file_path.endswith(".go") and not file_path.endswith("_test.go"):
            file_dir = str(PurePosixPath(file_path).parent)
            if file_dir == relative:
                return file_path

    return None


def _parse_go_module(go_mod_content: str) -> str | None:
    """Extract the module path from go.mod content.

    Parses the `module` directive, e.g.:
        module github.com/user/repo
    """
    for line in go_mod_content.splitlines():
        line = line.strip()
        if line.startswith("module "):
            return line[len("module ") :].strip()
    return None


# ---------------------------------------------------------------------------
# Python-specific resolver
# ---------------------------------------------------------------------------


def resolve_python_import(
    importer_path: str,
    import_source: str,
    available_files: set[str],
    *,
    is_relative: bool = False,
) -> str | None:
    """Resolve a Python import to a file path.

    Handles:
    - Relative imports: from . import foo → same directory
    - Relative with dots: from ..utils import bar → go up one directory
    - Absolute internal imports: match against project package names

    Args:
        importer_path: Path of the importing file (e.g., "app/services/user.py").
        import_source: The import source (e.g., ".models", "..utils", "app.models").
        available_files: Set of all project-relative file paths.
        is_relative: Whether this is a relative import (starts with .).

    Returns:
        Resolved file path or None.
    """
    if is_relative or import_source.startswith("."):
        return _resolve_python_relative(importer_path, import_source, available_files)

    # Absolute import — try to match as internal package path
    return _resolve_python_absolute(
        import_source,
        available_files,
        importer_path=importer_path,
    )


def _resolve_python_relative(
    importer_path: str,
    import_source: str,
    available_files: set[str],
) -> str | None:
    """Resolve Python relative imports (e.g., from . import foo, from ..utils import bar)."""
    # Count leading dots
    dots = 0
    for ch in import_source:
        if ch == ".":
            dots += 1
        else:
            break

    # The module part after the dots
    module_part = import_source[dots:]

    # Start from importer's directory
    importer_dir = PurePosixPath(importer_path).parent

    # Go up (dots - 1) directories (one dot = current package)
    current = importer_dir
    for _ in range(dots - 1):
        current = current.parent

    # Build the target path
    if module_part:
        # Convert dots in module name to path separators
        module_as_path = module_part.replace(".", "/")
        target = str(current / module_as_path)
    else:
        target = str(current)

    # Normalize
    target = str(PurePosixPath(os.path.normpath(target)))
    if target.startswith("./"):
        target = target[2:]

    # Try .py file
    py_candidate = f"{target}.py"
    if py_candidate in available_files:
        return py_candidate

    # Try __init__.py (package)
    init_candidate = f"{target}/__init__.py"
    if init_candidate in available_files:
        return init_candidate

    return None


def _shared_directory_count(left: str, right: str) -> int:
    """How many leading path segments the two project-relative paths share."""
    shared = 0
    for part_a, part_b in zip(PurePosixPath(left).parts, PurePosixPath(right).parts, strict=False):
        if part_a != part_b:
            break
        shared += 1
    return shared


def _resolve_python_absolute(
    import_source: str,
    available_files: set[str],
    importer_path: str = "",
) -> str | None:
    """Resolve an absolute Python import against project files.

    Converts a dotted module to path segments and matches a file that ends
    on those segments. ``app.config`` matches ``app/config.py`` and also
    ``apps/server/app/config.py``. It does not match ``myapp/config.py``.

    When several files match, the one that shares the longest directory
    prefix with the importer wins. A tie resolves to nothing: guessing
    between two packages would put the wrong module in the docs graph.
    A module file (``x.py``) wins over ``x/__init__.py`` at the same distance.
    """
    as_path = import_source.replace(".", "/")
    module_file = f"{as_path}.py"
    package_init = f"{as_path}/__init__.py"
    suffixes = (module_file, package_init)

    candidates = [
        path
        for path in available_files
        if any(path == suffix or path.endswith("/" + suffix) for suffix in suffixes)
    ]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    def sort_key(path: str) -> tuple[int, int]:
        module_rank = 1 if path.endswith(module_file) else 0
        return (_shared_directory_count(importer_path, path), module_rank)

    ranked = sorted(candidates, key=sort_key, reverse=True)
    best_key = sort_key(ranked[0])
    if sum(1 for path in ranked if sort_key(path) == best_key) > 1:
        return None
    return ranked[0]
