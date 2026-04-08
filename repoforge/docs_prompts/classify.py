"""Project and layer classification logic."""

from __future__ import annotations


def classify_project(repo_map) -> str:
    """
    Classify a project into one of the known types based on structural signals.

    Uses tech_stack, config_files, entry_points, module paths, and file counts.
    Returns a string key like "web_service", "cli_tool", etc.

    Deliberately NOT import-based — works for any language.
    """
    stack       = " ".join(repo_map.get("tech_stack", [])).lower()
    configs     = " ".join(repo_map.get("config_files", [])).lower()
    entries     = " ".join(repo_map.get("entry_points", [])).lower()
    layers      = repo_map.get("layers", {})
    total_files = repo_map.get("stats", {}).get("total_files", 0)

    all_paths = " ".join(
        m["path"].lower()
        for ld in layers.values()
        for m in ld.get("modules", [])
    )
    all_names = " ".join(
        m["name"].lower()
        for ld in layers.values()
        for m in ld.get("modules", [])
    )

    # --- Monorepo: multiple distinct layers (frontend + backend, etc.)
    if len(layers) >= 3:
        return "monorepo"
    has_frontend_layer = any(
        k in ("frontend", "web", "client", "ui") for k in layers
    )
    has_backend_layer = any(
        k in ("backend", "api", "server") for k in layers
    )
    if has_frontend_layer and has_backend_layer:
        return "monorepo"

    # --- Infrastructure / DevOps
    infra_signals = (
        "terraform", "helm", "ansible", "pulumi", "cdk",
        "dockerfile", "docker-compose", ".tf", ".hcl",
        "kubernetes", "k8s",
    )
    if any(s in configs or s in stack or s in all_paths for s in infra_signals):
        return "infra_devops"

    # --- Mobile
    mobile_signals = (
        "react native", "flutter", "expo", "swift", "kotlin",
        "android", "ios", "capacitor", "ionic",
    )
    if any(s in stack for s in mobile_signals):
        return "mobile_app"

    # --- Desktop
    desktop_signals = ("electron", "qt", "gtk", "tauri", "winforms", "wpf", "maui")
    if any(s in stack or s in configs for s in desktop_signals):
        return "desktop_app"

    # --- Data science / ML
    ds_signals = (
        "jupyter", "notebook", "sklearn", "tensorflow", "pytorch",
        "keras", "pandas", "numpy", "mlflow", "hugging", "llm",
        "langchain", "onnx", "spark", "dask",
    )
    ds_paths = ("train", "model", "notebook", "dataset", "pipeline", "experiment")
    if any(s in stack for s in ds_signals):
        return "data_science"
    if any(s in all_paths or s in all_names for s in ds_paths):
        # Only classify as data_science if no clear web signals
        web_counter = sum(1 for s in ("server", "api", "handler", "controller", "route") if s in all_paths)
        if web_counter == 0:
            return "data_science"

    # --- Frontend SPA (no backend layer)
    frontend_signals = (
        "react", "vue", "angular", "svelte", "next.js", "nuxt",
        "vite", "remix", "astro",
    )
    if any(s in stack for s in frontend_signals):
        # If it also has server code it's web_service or monorepo
        if not any(s in all_paths for s in ("server", "api", "handler", "controller")):
            return "frontend_app"

    # --- CLI tool
    cli_signals_stack = ("click", "cobra", "clap", "argparse", "typer", "commander")
    cli_signals_path  = ("cmd", "command", "cli", "bin")
    cli_entry          = ("cli", "cmd", "bin")
    if any(s in stack for s in cli_signals_stack):
        return "cli_tool"
    if any(s in all_paths for s in cli_signals_path):
        # CLI + no web = CLI tool
        if not any(s in all_paths for s in ("server", "handler", "controller", "route")):
            return "cli_tool"
    if any(s in entries for s in cli_entry) and total_files < 20:
        return "cli_tool"

    # --- Library / SDK: no entry points, meant to be imported
    if not entries and total_files < 30:
        # Has exports but no "main" / "server" entry
        if not any(s in all_paths for s in ("server", "api", "handler", "controller")):
            return "library_sdk"

    # --- Web service (default for anything with server signals)
    web_signals = (
        "server", "api", "handler", "controller", "route", "endpoint",
        "middleware", "graphql", "grpc", "rest", "http",
    )
    if any(s in all_paths or s in all_names for s in web_signals):
        return "web_service"

    if any(s in entries for s in ("main", "app", "server", "index")):
        return "web_service"

    # --- Fallback
    return "generic"


def classify_layer(layer_name: str, layer_data: dict, repo_map: dict) -> str:
    """
    Classify a single monorepo layer into a project type.

    Uses the layer's own modules + its name as primary signals.
    Falls back to classify_project() logic but scoped to this layer.
    """
    name_lower  = layer_name.lower()
    modules     = layer_data.get("modules", [])
    stack_all   = " ".join(repo_map.get("tech_stack", [])).lower()

    all_paths = " ".join(m["path"].lower() for m in modules)
    all_langs = " ".join(m.get("language", "") for m in modules).lower()
    num_files = len(modules)

    # --- Layer name hints (most reliable signal)
    frontend_names = ("frontend", "web", "client", "ui", "app", "spa", "portal")
    backend_names  = ("backend", "api", "server", "service", "core", "domain")
    infra_names    = ("infra", "infrastructure", "terraform", "helm", "k8s",
                      "deploy", "ops", "devops", "cloud")
    mobile_names   = ("mobile", "app", "ios", "android", "native")
    cli_names      = ("cli", "cmd", "tool", "bin", "script")
    shared_names   = ("shared", "common", "lib", "libs", "packages",
                      "pkg", "utils", "core", "types")
    data_names     = ("data", "ml", "ai", "model", "train", "notebook",
                      "analytics", "pipeline", "etl")
    docs_names     = ("docs", "documentation", "wiki")

    if any(n in name_lower for n in frontend_names):
        return "frontend_app"
    if any(n in name_lower for n in infra_names):
        return "infra_devops"
    if any(n in name_lower for n in mobile_names):
        return "mobile_app"
    if any(n in name_lower for n in cli_names):
        return "cli_tool"
    if any(n in name_lower for n in data_names):
        return "data_science"
    if any(n in name_lower for n in shared_names):
        return "library_sdk"
    if any(n in name_lower for n in docs_names):
        return "generic"

    # --- Language / framework signals within this layer
    if any(fw in stack_all for fw in ("react", "vue", "angular", "svelte", "next")):
        if any(fw in all_paths or fw in all_langs for fw in ("tsx", "jsx", "vue", "svelte")):
            return "frontend_app"
    if any(fw in stack_all for fw in ("terraform", "helm", "ansible", "pulumi")):
        if any(ext in all_paths for ext in (".tf", "helm", "ansible", "k8s")):
            return "infra_devops"
    if any(fw in stack_all for fw in ("expo", "react native", "flutter", "swift", "kotlin")):
        return "mobile_app"

    # --- Path-based signals inside the layer
    if any(p in all_paths for p in ("controller", "handler", "route", "endpoint", "router")):
        return "web_service"
    if any(p in all_paths for p in ("component", "screen", "page", "widget")):
        if any(p in all_paths for p in ("store", "hook", "context", "redux")):
            return "frontend_app"
    if any(p in all_paths for p in ("train", "model", "pipeline", "dataset")):
        return "data_science"
    if any(p in all_paths for p in ("cmd", "command", "flag", "arg")):
        return "cli_tool"

    # --- Default for backend-named layers
    if any(n in name_lower for n in backend_names):
        return "web_service"

    # --- Fallback: use file count and content
    if num_files >= 5:
        return "web_service"   # most likely for a substantial unknown layer
    return "library_sdk"       # small layer = probably a shared lib


def _layer_repo_map(layer_name: str, layer_data: dict, repo_map: dict) -> dict:
    """
    Build a scoped repo_map for a single layer.
    Preserves global tech_stack and config_files (they apply to all layers).
    """
    return {
        "root":         repo_map.get("root", ""),
        "tech_stack":   repo_map.get("tech_stack", []),
        "entry_points": [
            ep for ep in repo_map.get("entry_points", [])
            if layer_data.get("path", layer_name) in ep
               or ep.startswith(layer_name)
        ],
        "config_files": repo_map.get("config_files", []),
        "layers":       {layer_name: layer_data},
        "stats": {
            "total_files": len(layer_data.get("modules", [])),
            "by_extension": {},
            "rg_available": repo_map.get("stats", {}).get("rg_available", False),
            "rg_version":   repo_map.get("stats", {}).get("rg_version", None),
        },
    }
