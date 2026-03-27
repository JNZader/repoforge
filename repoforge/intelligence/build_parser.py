"""
build_parser.py — Parse build/manifest files to extract project metadata.

Supports: go.mod, package.json, pyproject.toml, Cargo.toml.
Pure Python — no native dependencies required.

Why this exists:
  Scanner's layer detection uses directory name heuristics, which misses
  internal packages that don't match conventional names. Build files are
  the authoritative source of module structure.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class BuildInfo:
    """Metadata extracted from build/manifest files."""

    language: str = ""
    """Primary language: 'go', 'python', 'typescript', 'rust', etc."""

    module_path: str | None = None
    """Root module path, e.g. 'github.com/Gentleman-Programming/engram'."""

    version: str | None = None
    """Project version from the manifest."""

    go_version: str | None = None
    """Go version from go.mod (Go projects only)."""

    packages: list[str] = field(default_factory=list)
    """Internal packages/modules discovered."""

    dependencies: list[str] = field(default_factory=list)
    """External (direct) dependencies."""

    dev_dependencies: list[str] = field(default_factory=list)
    """Dev/test dependencies."""

    entry_points: list[str] = field(default_factory=list)
    """Main files, bin entries, CLI commands."""

    scripts: dict[str, str] = field(default_factory=dict)
    """npm scripts, Makefile targets, etc."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_build_files(root_dir: str) -> BuildInfo:
    """
    Parse all recognized manifest files under root_dir.

    Tries each parser in order and returns the first successful result.
    For monorepos with multiple manifests, the first match wins
    (go.mod > package.json > pyproject.toml > Cargo.toml).

    Args:
        root_dir: Absolute path to the repository root.

    Returns:
        BuildInfo with extracted metadata. Returns empty BuildInfo
        if no manifest files are found (graceful degradation).
    """
    root = Path(root_dir).resolve()

    parsers = [
        ("go.mod", _parse_go_mod),
        ("package.json", _parse_package_json),
        ("pyproject.toml", _parse_pyproject_toml),
        ("Cargo.toml", _parse_cargo_toml),
    ]

    for filename, parser in parsers:
        manifest = root / filename
        if manifest.exists():
            try:
                info = parser(manifest, root)
                if info.language:
                    logger.debug("Parsed %s -> language=%s, %d packages",
                                 filename, info.language, len(info.packages))
                    return info
            except Exception as e:
                logger.warning("Failed to parse %s: %s", manifest, e)

    logger.debug("No recognized manifest files found in %s", root)
    return BuildInfo()


# ---------------------------------------------------------------------------
# go.mod parser
# ---------------------------------------------------------------------------

def _parse_go_mod(path: Path, root: Path) -> BuildInfo:
    """Parse go.mod for module path, Go version, and dependencies."""
    content = path.read_text(errors="replace")
    info = BuildInfo(language="go")

    # Module path: "module github.com/org/repo"
    m = re.search(r"^module\s+(\S+)", content, re.MULTILINE)
    if m:
        info.module_path = m.group(1)

    # Go version: "go 1.21" or "go 1.21.0"
    m = re.search(r"^go\s+(\S+)", content, re.MULTILINE)
    if m:
        info.go_version = m.group(1)

    # Dependencies from require blocks
    # Handles both single-line "require pkg v1.0" and block "require (\n...\n)"
    direct_deps: list[str] = []
    indirect_deps: list[str] = []

    # Block require
    for block_match in re.finditer(
        r"require\s*\((.*?)\)", content, re.DOTALL
    ):
        block = block_match.group(1)
        for line in block.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                dep = parts[0]
                is_indirect = "// indirect" in line
                if is_indirect:
                    indirect_deps.append(dep)
                else:
                    direct_deps.append(dep)

    # Single-line require
    for m in re.finditer(r"^require\s+(\S+)\s+\S+", content, re.MULTILINE):
        dep = m.group(1)
        if dep != "(":
            direct_deps.append(dep)

    info.dependencies = list(dict.fromkeys(direct_deps))

    # Discover internal Go packages by scanning directories
    info.packages = _discover_go_packages(root, info.module_path)

    # Entry points: cmd/ directories are conventional Go entry points
    cmd_dir = root / "cmd"
    if cmd_dir.exists():
        for child in sorted(cmd_dir.iterdir()):
            if child.is_dir():
                main_go = child / "main.go"
                if main_go.exists():
                    info.entry_points.append(str(child.relative_to(root)))

    # Also check root main.go
    if (root / "main.go").exists():
        info.entry_points.append("main.go")

    return info


def _discover_go_packages(root: Path, module_path: str | None) -> list[str]:
    """
    Discover Go packages by scanning for directories containing .go files.

    Returns relative paths from root (e.g., 'internal/store', 'cmd/engram').
    """
    packages: list[str] = []
    skip_dirs = {
        ".git", "node_modules", "vendor", "testdata",
        "__pycache__", ".venv", "dist", "build",
    }

    try:
        for entry in sorted(root.rglob("*.go")):
            try:
                rel_parts = entry.relative_to(root).parts
            except ValueError:
                continue
            if any(part in skip_dirs for part in rel_parts):
                continue
            if entry.name.endswith("_test.go"):
                continue
            # Package = directory containing the .go file
            pkg_dir = str(entry.parent.relative_to(root))
            if pkg_dir == ".":
                pkg_dir = "."  # root package
            if pkg_dir not in packages:
                packages.append(pkg_dir)
    except PermissionError:
        pass

    return packages


# ---------------------------------------------------------------------------
# package.json parser
# ---------------------------------------------------------------------------

def _parse_package_json(path: Path, root: Path) -> BuildInfo:
    """Parse package.json for name, version, deps, scripts, and workspaces."""
    data = json.loads(path.read_text(errors="replace"))
    info = BuildInfo(language="typescript")

    info.module_path = data.get("name")
    info.version = data.get("version")

    # Dependencies
    info.dependencies = list(data.get("dependencies", {}).keys())
    info.dev_dependencies = list(data.get("devDependencies", {}).keys())

    # Scripts
    info.scripts = dict(data.get("scripts", {}))

    # Entry points
    main = data.get("main")
    if main:
        info.entry_points.append(main)
    bin_field = data.get("bin")
    if isinstance(bin_field, dict):
        info.entry_points.extend(bin_field.values())
    elif isinstance(bin_field, str):
        info.entry_points.append(bin_field)

    # Exports field
    exports = data.get("exports")
    if isinstance(exports, dict):
        for key, val in exports.items():
            if isinstance(val, str):
                info.entry_points.append(val)
            elif isinstance(val, dict):
                # e.g. {"import": "./dist/index.mjs", "require": "./dist/index.cjs"}
                for v in val.values():
                    if isinstance(v, str) and v not in info.entry_points:
                        info.entry_points.append(v)

    # Workspace packages
    workspaces = data.get("workspaces", [])
    if isinstance(workspaces, dict):
        # yarn workspaces: {"packages": ["packages/*"]}
        workspaces = workspaces.get("packages", [])

    info.packages = _resolve_workspace_globs(root, workspaces)

    # If no workspaces, discover packages from src/ structure
    if not info.packages:
        info.packages = _discover_ts_packages(root)

    # Detect language more precisely (JS vs TS)
    has_ts = (
        "typescript" in info.dev_dependencies
        or "typescript" in info.dependencies
        or (root / "tsconfig.json").exists()
    )
    if not has_ts:
        info.language = "javascript"

    return info


def _resolve_workspace_globs(root: Path, patterns: list) -> list[str]:
    """Resolve workspace glob patterns like 'packages/*' to actual directories."""
    packages: list[str] = []
    for pattern in patterns:
        if not isinstance(pattern, str):
            continue
        # Simple glob: "packages/*" -> list directories matching
        if "*" in pattern:
            base = pattern.split("*")[0].rstrip("/")
            base_path = root / base
            if base_path.exists():
                for child in sorted(base_path.iterdir()):
                    if child.is_dir() and (child / "package.json").exists():
                        packages.append(str(child.relative_to(root)))
        else:
            # Exact path
            candidate = root / pattern
            if candidate.exists() and candidate.is_dir():
                packages.append(pattern)
    return packages


def _discover_ts_packages(root: Path) -> list[str]:
    """Discover TypeScript/JavaScript source directories."""
    packages: list[str] = []
    candidates = ["src", "lib", "app", "pages", "components"]
    for name in candidates:
        d = root / name
        if d.exists() and d.is_dir():
            packages.append(name)
    return packages


# ---------------------------------------------------------------------------
# pyproject.toml parser
# ---------------------------------------------------------------------------

def _parse_pyproject_toml(path: Path, root: Path) -> BuildInfo:
    """
    Parse pyproject.toml for project metadata.

    Uses naive line-by-line parsing to avoid requiring a TOML library
    (Python 3.10 doesn't have tomllib in stdlib, and we don't want deps).
    Python 3.11+ has tomllib but we support 3.10+.
    """
    content = path.read_text(errors="replace")
    info = BuildInfo(language="python")

    # Try tomllib (3.11+) first for accurate parsing
    try:
        import tomllib
        data = tomllib.loads(content)
        return _build_info_from_toml_dict(data, root)
    except ImportError:
        pass

    # Fallback: regex-based parsing for 3.10
    # Name
    m = re.search(r'^name\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if m:
        info.module_path = m.group(1)

    # Version
    m = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if m:
        info.version = m.group(1)

    # Dependencies from [project] dependencies array
    deps_match = re.search(
        r'\[project\].*?^dependencies\s*=\s*\[(.*?)\]',
        content, re.DOTALL | re.MULTILINE
    )
    if deps_match:
        deps_block = deps_match.group(1)
        for dep_m in re.finditer(r'"([^"]+)"', deps_block):
            dep_name = re.split(r'[>=<!\[;]', dep_m.group(1))[0].strip()
            if dep_name:
                info.dependencies.append(dep_name)

    # Entry points from [project.scripts]
    in_scripts = False
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped == "[project.scripts]":
            in_scripts = True
            continue
        if in_scripts:
            if stripped.startswith("["):
                break
            if "=" in stripped and not stripped.startswith("#"):
                parts = stripped.split("=", 1)
                cmd = parts[0].strip()
                target = parts[1].strip().strip('"\'')
                info.scripts[cmd] = target
                # Convert module path to file path
                if ":" in target:
                    mod = target.split(":")[0].replace(".", "/") + ".py"
                    if (root / mod).exists():
                        info.entry_points.append(mod)

    # Discover Python packages
    info.packages = _discover_python_packages(root)

    return info


def _build_info_from_toml_dict(data: dict, root: Path) -> BuildInfo:
    """Build BuildInfo from a parsed TOML dict (Python 3.11+ path)."""
    info = BuildInfo(language="python")

    project = data.get("project", {})
    info.module_path = project.get("name")
    info.version = project.get("version")

    # Dependencies
    for dep in project.get("dependencies", []):
        dep_name = re.split(r'[>=<!\[;]', dep)[0].strip()
        if dep_name:
            info.dependencies.append(dep_name)

    # Optional/dev dependencies
    opt_deps = project.get("optional-dependencies", {})
    for group_deps in opt_deps.values():
        for dep in group_deps:
            dep_name = re.split(r'[>=<!\[;]', dep)[0].strip()
            if dep_name:
                info.dev_dependencies.append(dep_name)

    # Scripts
    scripts = project.get("scripts", {})
    info.scripts = dict(scripts)
    for cmd, target in scripts.items():
        if ":" in target:
            mod = target.split(":")[0].replace(".", "/") + ".py"
            if (root / mod).exists():
                info.entry_points.append(mod)

    # Discover Python packages
    info.packages = _discover_python_packages(root)

    return info


def _discover_python_packages(root: Path) -> list[str]:
    """
    Discover Python packages by looking for directories with __init__.py.
    """
    packages: list[str] = []
    skip_dirs = {
        ".git", "node_modules", "__pycache__", ".venv", "venv",
        "dist", "build", ".pytest_cache", ".mypy_cache", ".ruff_cache",
        ".tox", ".eggs", "*.egg-info",
    }

    try:
        for init_file in sorted(root.rglob("__init__.py")):
            try:
                rel = str(init_file.parent.relative_to(root))
            except ValueError:
                continue
            parts = rel.split("/")
            if any(part in skip_dirs or part.endswith(".egg-info") for part in parts):
                continue
            if rel != "." and rel not in packages:
                packages.append(rel)
    except PermissionError:
        pass

    return packages


# ---------------------------------------------------------------------------
# Cargo.toml parser
# ---------------------------------------------------------------------------

def _parse_cargo_toml(path: Path, root: Path) -> BuildInfo:
    """Parse Cargo.toml for Rust project metadata."""
    content = path.read_text(errors="replace")
    info = BuildInfo(language="rust")

    # [package] name and version
    m = re.search(r'\[package\].*?^name\s*=\s*"([^"]+)"',
                  content, re.DOTALL | re.MULTILINE)
    if m:
        info.module_path = m.group(1)

    m = re.search(r'\[package\].*?^version\s*=\s*"([^"]+)"',
                  content, re.DOTALL | re.MULTILINE)
    if m:
        info.version = m.group(1)

    # [dependencies] section
    in_deps = False
    in_dev_deps = False
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped == "[dependencies]":
            in_deps = True
            in_dev_deps = False
            continue
        elif stripped == "[dev-dependencies]":
            in_dev_deps = True
            in_deps = False
            continue
        elif stripped.startswith("["):
            in_deps = False
            in_dev_deps = False
            continue

        if (in_deps or in_dev_deps) and "=" in stripped and not stripped.startswith("#"):
            dep_name = stripped.split("=")[0].strip()
            if dep_name:
                if in_dev_deps:
                    info.dev_dependencies.append(dep_name)
                else:
                    info.dependencies.append(dep_name)

    # Workspace members
    workspace_match = re.search(
        r'\[workspace\].*?^members\s*=\s*\[(.*?)\]',
        content, re.DOTALL | re.MULTILINE
    )
    if workspace_match:
        members_block = workspace_match.group(1)
        for m in re.finditer(r'"([^"]+)"', members_block):
            member = m.group(1)
            if "*" in member:
                # Glob pattern like "crates/*"
                base = member.split("*")[0].rstrip("/")
                base_path = root / base
                if base_path.exists():
                    for child in sorted(base_path.iterdir()):
                        if child.is_dir() and (child / "Cargo.toml").exists():
                            info.packages.append(str(child.relative_to(root)))
            else:
                candidate = root / member
                if candidate.exists():
                    info.packages.append(member)

    # Entry points: src/main.rs
    if (root / "src" / "main.rs").exists():
        info.entry_points.append("src/main.rs")

    # Discover Rust crate modules
    if not info.packages:
        info.packages = _discover_rust_modules(root)

    return info


def _discover_rust_modules(root: Path) -> list[str]:
    """Discover Rust source modules under src/."""
    modules: list[str] = []
    src = root / "src"
    if not src.exists():
        return modules

    for rs_file in sorted(src.rglob("*.rs")):
        try:
            rel = str(rs_file.relative_to(root))
        except ValueError:
            continue
        # Each .rs file in src/ is a module
        mod = rel.replace(".rs", "").replace("/", "::")
        if mod not in modules:
            modules.append(rel)

    return modules
