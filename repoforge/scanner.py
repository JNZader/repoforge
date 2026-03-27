"""
scanner.py - Deterministic repo analysis. No LLM involved.

Responsibilities:
- Discover project structure and layer boundaries
- Extract module summaries (imports, exports, key functions/classes)
- Detect tech stack from package manifests
- Respect .gitignore patterns (via ripgrep when available)

Output is a RepoMap dict consumed by generator.py

File discovery + definition extraction uses ripgrep when installed
(brew install ripgrep / sudo apt install ripgrep / scoop install ripgrep).
Falls back to pure Python rglob + regex automatically.
"""

import json
import ast
import logging
from pathlib import Path
from typing import Optional
import yaml

logger = logging.getLogger(__name__)

# Imported lazily inside functions to avoid circular import at module level
# from .ripgrep import list_files, extract_definitions, extract_imports, extract_summary_hints


# ---------------------------------------------------------------------------
# Layer detection heuristics
# Override via codeviewx.yaml or repoforge.yaml in repo root
# ---------------------------------------------------------------------------

LAYER_PATTERNS = {
    "frontend": [
        # Explicit names first (most specific)
        "apps/web", "apps/frontend", "packages/ui",
        "frontend", "web", "client", "ui",
        # Wildcard-style: any dir with these names
        "consorcio-web", "app-web", "webapp",
        "src/pages", "src/components", "src/app",
    ],
    "backend": [
        "apps/api", "apps/server", "apps/backend",
        "backend", "api", "server", "gee-backend",
        "src/api", "src/server",
    ],
    "shared": [
        "packages/shared", "packages/common", "packages/core",
        "shared", "common", "lib", "libs", "packages",
    ],
    "infra": [
        # Only explicit infra dirs — NOT .github/workflows (too broad)
        "infra", "infrastructure", "deploy",
        "terraform", "helm", "k8s",
        "nginx", "docker",
    ],
    "workers": [
        "workers", "jobs", "tasks", "queues", "celery",
    ],
    "mobile": [
        "mobile", "ios", "android", "app",
    ],
}

# Dirs that are never layers even if they match patterns
NEVER_LAYERS = {
    ".github", ".github/workflows", "node_modules", "__pycache__",
    ".venv", "venv", "dist", "build", ".next", ".nuxt",
    "coverage", ".pytest_cache", "docs", "nginx", "vendor",
}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".next", ".nuxt", "coverage", ".pytest_cache", ".mypy_cache", "vendor",
}

SUPPORTED_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb",
    ".cs", ".cpp", ".c", ".h", ".php", ".swift", ".kt",
}

MAX_FILE_SIZE = 100 * 1024  # 100KB per file

# Previously hardcoded to 80, which silently dropped files from large layers.
# Now defaults to 500 — large enough for most repos while still providing a
# safety rail. Override via --max-files CLI flag or repoforge.yaml config.
# The real token budget enforcement happens downstream in graph_context.py
# (intelligence engine's budget.py when available), so this cap only limits
# the scan phase, not the final output.
DEFAULT_MAX_FILES_PER_LAYER = 500


# ---------------------------------------------------------------------------
# Complexity classification (deterministic, no LLM)
# ---------------------------------------------------------------------------

def classify_complexity(repo_map: dict, override: str = "auto") -> dict:
    """
    Classify repo complexity and return routing parameters.

    Adjusts generation behavior so small repos get detailed treatment
    and large repos get concise, focused output.

    Args:
        repo_map: Output from scan_repo()
        override: "auto" (detect), or force "small" / "medium" / "large"

    Returns:
        Dict with size classification and all routing parameters.
    """
    total_files = repo_map.get("stats", {}).get("total_files", 0)
    num_layers = len(repo_map.get("layers", {}))
    total_modules = sum(
        len(layer.get("modules", {}))
        for layer in repo_map.get("layers", {}).values()
    )

    # Classify
    if override != "auto" and override in ("small", "medium", "large"):
        size = override
    elif total_files <= 20 and num_layers <= 2:
        size = "small"
    elif total_files <= 200 and num_layers <= 5:
        size = "medium"
    else:
        size = "large"

    return {
        # Classification
        "size": size,
        "total_files": total_files,
        "num_layers": num_layers,
        "total_modules": total_modules,
        # Skills generation parameters
        "max_module_skills_per_layer": {"small": 10, "medium": 5, "large": 3}[size],
        "min_exports_for_skill": {"small": 1, "medium": 2, "large": 3}[size],
        "prompt_detail": {"small": "detailed", "medium": "standard", "large": "concise"}[size],
        "generate_orchestrator": size != "small",
        "generate_layer_agents": size != "small",
        "max_files_per_layer": {"small": 200, "medium": 150, "large": 100}[size],
        # Docs generation parameters
        "max_chapters": {"small": 5, "medium": 7, "large": 9}[size],
        "include_monorepo_hierarchy": size == "large",
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def scan_repo(
    working_dir: str,
    config: Optional[dict] = None,
    max_files_per_layer: Optional[int] = None,
) -> dict:
    """
    Scan a repo and return a RepoMap dict.

    Args:
        working_dir: Path to the repo root.
        config: Optional repoforge.yaml config dict.
        max_files_per_layer: Cap on files per layer. Defaults to
            DEFAULT_MAX_FILES_PER_LAYER (500). Pass 0 or None to use
            the default. The old hardcoded cap of 80 silently dropped
            files — we now default to 500 because token-budgeted
            selection downstream handles the real output limits.

    RepoMap structure:
    {
        "root": str,
        "tech_stack": list[str],
        "layers": {
            "backend": {
                "path": str,
                "modules": [
                    {
                        "path": str,           # relative path
                        "name": str,
                        "language": str,
                        "exports": list[str],  # public functions/classes
                        "imports": list[str],  # external deps imported
                        "summary_hint": str,   # short description from docstring/comments
                    }
                ]
            },
            ...
        },
        "entry_points": list[str],
        "config_files": list[str],
        "repoforge_config": dict,   # raw repoforge.yaml content (if found)
        "stats": {
            "total_files": int,
            "rg_available": bool,
            "rg_version": str | None,
        }
    }
    """
    from .ripgrep import repo_stats

    root = Path(working_dir).resolve()
    config = config or _load_config(root)

    # Resolve max files: CLI flag > config > default
    effective_max = max_files_per_layer or config.get(
        "max_files_per_layer", DEFAULT_MAX_FILES_PER_LAYER
    )

    tech_stack = _detect_tech_stack(root)
    layers = _detect_layers(root, config, effective_max)
    entry_points = _find_entry_points(root)
    config_files = _find_config_files(root)
    stats = repo_stats(root)

    return {
        "root": str(root),
        "tech_stack": tech_stack,
        "layers": layers,
        "entry_points": entry_points,
        "config_files": config_files,
        "repoforge_config": config,   # expose so generator/docs_generator can read
        "stats": stats,
    }


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _load_config(root: Path) -> dict:
    for name in ("repoforge.yaml", "repoforge.yml", "codeviewx.yaml"):
        p = root / name
        if p.exists():
            with open(p) as f:
                return yaml.safe_load(f) or {}
    return {}


# ---------------------------------------------------------------------------
# Tech stack detection
# ---------------------------------------------------------------------------

def _detect_tech_stack(root: Path) -> list:
    stack = []

    # Check root AND one level deep (for monorepos like gee-backend/requirements.txt)
    search_roots = [root] + [p for p in root.iterdir() if p.is_dir() and p.name not in {
        ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
        ".next", ".nuxt", "coverage", "docs", "nginx", ".github",
    }]

    checks = {
        "Python": ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"],
        "Node.js": ["package.json"],
        "Go": ["go.mod"],
        "Rust": ["Cargo.toml"],
        "Java": ["pom.xml", "build.gradle"],
        "Ruby": ["Gemfile"],
        "PHP": ["composer.json"],
    }

    for lang, markers in checks.items():
        for search_root in search_roots:
            if any((search_root / m).exists() for m in markers):
                stack.append(lang)
                break  # found this lang, stop searching subdirs

    # Framework hints from ANY package.json found
    for search_root in search_roots:
        pkg = search_root / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text())
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                if "next" in deps:
                    stack.append("Next.js")
                if "react" in deps:
                    stack.append("React")
                if "vue" in deps:
                    stack.append("Vue")
                if "svelte" in deps:
                    stack.append("Svelte")
                if "express" in deps:
                    stack.append("Express")
                if "fastify" in deps:
                    stack.append("Fastify")
                if "vite" in deps:
                    stack.append("Vite")
                if "@mantine" in " ".join(deps.keys()):
                    stack.append("Mantine UI")
                if "leaflet" in deps:
                    stack.append("Leaflet")
                if "zustand" in deps:
                    stack.append("Zustand")
                if "supabase" in " ".join(deps.keys()):
                    stack.append("Supabase")
            except Exception as e:
                logger.debug("Failed to parse package.json %s: %s", p, e)

    # Python framework hints — search all subdirs
    for search_root in search_roots:
        for fname in ["requirements.txt", "pyproject.toml"]:
            p = search_root / fname
            if p.exists():
                try:
                    txt = p.read_text().lower()
                    if "fastapi" in txt:
                        stack.append("FastAPI")
                    if "django" in txt:
                        stack.append("Django")
                    if "flask" in txt:
                        stack.append("Flask")
                    if "langchain" in txt:
                        stack.append("LangChain")
                    if "celery" in txt:
                        stack.append("Celery")
                    if "earthengine" in txt or "earthengine-api" in txt:
                        stack.append("Google Earth Engine")
                    if "supabase" in txt:
                        stack.append("Supabase")
                    if "redis" in txt:
                        stack.append("Redis")
                except Exception as e:
                    logger.debug("Failed to parse Python manifest %s: %s", p, e)

    # Docker / infra
    for search_root in search_roots:
        if (search_root / "Dockerfile").exists() or (search_root / "docker-compose.yml").exists():
            stack.append("Docker")
            break
    if (root / "terraform").exists():
        stack.append("Terraform")

    return list(dict.fromkeys(stack))  # dedupe, preserve order


# ---------------------------------------------------------------------------
# Layer detection
# ---------------------------------------------------------------------------

def _detect_layers(
    root: Path, config: dict, max_files: int = DEFAULT_MAX_FILES_PER_LAYER,
) -> dict:
    # Allow full override from config
    layer_map = config.get("layers", {})

    if not layer_map:
        # Auto-detect: walk LAYER_PATTERNS in priority order
        for layer, patterns in LAYER_PATTERNS.items():
            for pattern in patterns:
                candidate = root / pattern
                # Normalize to check against NEVER_LAYERS
                try:
                    rel = str(candidate.relative_to(root))
                except ValueError:
                    rel = pattern
                if rel in NEVER_LAYERS:
                    continue
                if candidate.exists() and candidate.is_dir():
                    if layer not in layer_map:
                        layer_map[layer] = str(candidate)
                    break

    # If nothing detected, treat root as a single "main" layer
    if not layer_map:
        layer_map["main"] = str(root)

    result = {}
    for layer_name, layer_path in layer_map.items():
        p = Path(layer_path) if Path(layer_path).is_absolute() else root / layer_path
        if p.exists():
            modules = _scan_layer(p, root, max_files)
            result[layer_name] = {
                "path": str(p.relative_to(root)),
                "modules": modules,
            }

    return result


def _scan_layer(
    layer_path: Path, root: Path, max_files: int = DEFAULT_MAX_FILES_PER_LAYER,
) -> list:
    from .ripgrep import (
        list_files,
        extract_definitions,
        extract_imports,
        extract_summary_hints,
        rg_available,
    )

    # 1. Discover files (rg respects .gitignore; fallback uses rglob)
    all_files = list_files(layer_path, max_size_kb=MAX_FILE_SIZE // 1024)
    files = all_files[:max_files]

    if len(all_files) > max_files:
        logger.warning(
            "Layer %s has %d files, capped at %d. "
            "Use --max-files to increase the limit.",
            layer_path, len(all_files), max_files,
        )

    if not files:
        return []

    # 2. Batch-extract definitions, imports, and summary hints
    #    rg does this in 1-3 subprocess calls total regardless of file count
    definitions = extract_definitions(files, root)   # {rel_path: [name, ...]}
    imports_map = extract_imports(files, root)        # {rel_path: [pkg, ...]}
    hints_map = extract_summary_hints(files, root)    # {rel_path: "hint text"}

    modules = []
    for fpath in files:
        ext = fpath.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue

        rel = str(fpath.relative_to(root))
        lang = _ext_to_language(ext)

        module = {
            "path": rel,
            "name": fpath.stem,
            "language": lang,
            "exports": definitions.get(rel, [])[:20],
            "imports": imports_map.get(rel, [])[:20],
            "summary_hint": hints_map.get(rel, ""),
        }

        # For Python: complement rg results with AST for better accuracy
        # (rg uses regex so it can miss some patterns; AST is authoritative)
        # Only do this when rg is NOT available (avoid double work)
        if ext == ".py" and not rg_available():
            try:
                content = fpath.read_text(errors="replace")
                _enrich_python(module, content)
            except Exception as e:
                logger.debug("Failed to enrich Python module %s: %s", fpath, e)
        elif ext in (".ts", ".tsx", ".js", ".jsx") and not rg_available():
            try:
                content = fpath.read_text(errors="replace")
                _enrich_js(module, content)
            except Exception as e:
                logger.debug("Failed to enrich JS/TS module %s: %s", fpath, e)

        modules.append(module)

    return modules


# ---------------------------------------------------------------------------
# Language-specific enrichment (deterministic, no LLM)
# ---------------------------------------------------------------------------

def _enrich_python(module: dict, content: str):
    try:
        tree = ast.parse(content)
    except SyntaxError:
        module["summary_hint"] = _extract_first_comment(content)
        return

    # Module docstring
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
    ):
        doc = tree.body[0].value.value
        module["summary_hint"] = doc.strip().split("\n")[0][:200]

    # Exports: top-level functions + classes
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                module["exports"].append(node.name)
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                module["exports"].append(node.name)

    # Imports: external packages only (not relative)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                pkg = alias.name.split(".")[0]
                if pkg not in module["imports"]:
                    module["imports"].append(pkg)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                pkg = node.module.split(".")[0]
                if pkg not in module["imports"]:
                    module["imports"].append(pkg)

    # Keep unique, cap at 20
    module["exports"] = list(dict.fromkeys(module["exports"]))[:20]
    module["imports"] = list(dict.fromkeys(module["imports"]))[:20]


def _enrich_js(module: dict, content: str):
    lines = content.split("\n")

    # Summary from JSDoc / first comment block
    module["summary_hint"] = _extract_first_comment(content)

    # Rough exports (export function / export class / export const)
    exports = []
    imports = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("export "):
            for kw in ("function ", "class ", "const ", "async function "):
                if kw in stripped:
                    name = stripped.split(kw)[-1].split("(")[0].split(" ")[0].split("{")[0]
                    if name and name.isidentifier():
                        exports.append(name)
        if stripped.startswith("import ") and " from " in stripped:
            src = stripped.split(" from ")[-1].strip().strip("'\"`;")
            if not src.startswith("."):
                pkg = src.split("/")[0].lstrip("@")
                if pkg:
                    imports.append(src.split("/")[0])

    module["exports"] = list(dict.fromkeys(exports))[:20]
    module["imports"] = list(dict.fromkeys(imports))[:20]


def _extract_first_comment(content: str) -> str:
    for line in content.split("\n")[:20]:
        stripped = line.strip()
        if stripped.startswith(("#", "//", "/*", "*", "---")):
            clean = stripped.lstrip("#/!* ").strip()
            if len(clean) > 10:
                return clean[:200]
    return ""


def _ext_to_language(ext: str) -> str:
    mapping = {
        ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
        ".js": "JavaScript", ".jsx": "JavaScript", ".go": "Go",
        ".rs": "Rust", ".java": "Java", ".rb": "Ruby", ".cs": "C#",
        ".cpp": "C++", ".c": "C", ".h": "C/C++", ".php": "PHP",
        ".swift": "Swift", ".kt": "Kotlin",
    }
    return mapping.get(ext, "Unknown")


# ---------------------------------------------------------------------------
# Entry points & config files
# ---------------------------------------------------------------------------

def _find_entry_points(root: Path) -> list:
    """
    Find likely entry points. Checks:
    1. pyproject.toml [project.scripts] — most reliable for Python packages
    2. package.json "main" and "bin" fields
    3. Common filename patterns as fallback
    """
    found = []

    # 1. pyproject.toml [project.scripts] → e.g. repoforge = "repoforge.cli:main"
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            txt = pyproject.read_text()
            # Find [project.scripts] section — parse naively (no toml dep needed)
            in_scripts = False
            for line in txt.split("\n"):
                stripped = line.strip()
                if stripped == "[project.scripts]":
                    in_scripts = True
                    continue
                if in_scripts:
                    if stripped.startswith("["):
                        break  # new section
                    if "=" in stripped and not stripped.startswith("#"):
                        # e.g. repoforge = "repoforge.cli:main"
                        cmd_name = stripped.split("=")[0].strip()
                        module_path = stripped.split("=", 1)[1].strip().strip('"\'\' ')
                        # Convert "repoforge.cli:main" -> "repoforge/cli.py"
                        if ":" in module_path:
                            mod = module_path.split(":")[0].replace(".", "/") + ".py"
                            if (root / mod).exists():
                                found.append(mod)
                            else:
                                found.append(f"{cmd_name} → {module_path}")
        except Exception as e:
            logger.debug("Failed to detect entrypoints from pyproject.toml: %s", e)

    # 2. package.json main/bin
    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text())
            if data.get("main"):
                found.append(data["main"])
            if isinstance(data.get("bin"), dict):
                found.extend(data["bin"].values())
            elif isinstance(data.get("bin"), str):
                found.append(data["bin"])
        except Exception as e:
            logger.debug("Failed to parse package.json for entrypoints: %s", e)

    # 3. Common filename fallbacks
    candidates = [
        "main.py", "app.py", "run.py", "wsgi.py", "asgi.py",
        "index.ts", "index.js", "src/main.ts", "src/main.js",
        "src/index.ts", "src/index.js", "src/app.ts",
        "cmd/main.go", "main.go",
        "manage.py",  # Django
        "artisan",    # Laravel
    ]
    for c in candidates:
        if (root / c).exists() and c not in found:
            found.append(c)

    return found


def _find_config_files(root: Path) -> list:
    candidates = [
        "pyproject.toml", "package.json", "go.mod", "Cargo.toml",
        "docker-compose.yml", "Dockerfile", ".env.example",
        "repoforge.yaml", "codeviewx.yaml",
    ]
    return [c for c in candidates if (root / c).exists()]
