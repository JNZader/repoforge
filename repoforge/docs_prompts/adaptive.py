"""Adaptive chapter prompt templates for project-type-specific chapters.

Each project type (cli_tool, web_service, library_sdk, etc.) has unique
chapters. This module generates the (system, user) prompt pair for each.
"""

from __future__ import annotations

import warnings

from .context import _repo_context
from .system import _base_system


def _adaptive_prompt(chapter_file: str, repo_map: dict, language: str,
                     project_name: str, project_type: str,
                     graph_context: str = "",
                     doc_chunks: dict | None = None) -> tuple[str, str]:
    """Generate prompts for project-type-specific chapters.

    .. deprecated::
        Use YAML templates instead. This function is the legacy fallback
        and will be removed in a future release.
    """
    warnings.warn(
        "_adaptive_prompt is deprecated, use YAML templates instead. "
        "See repoforge/templates/ for the new template format.",
        DeprecationWarning,
        stacklevel=2,
    )
    sys = _base_system(language)
    ctx = _repo_context(repo_map, graph_context=graph_context)

    # --- CLI: commands reference
    if chapter_file == "05-commands.md":
        user = f"""Generate **05-commands.md** — the Commands Reference for the CLI tool **{project_name}**.
{ctx}
## What this document must contain
1. `# Commands Reference` heading
2. **Usage pattern** — the general invocation pattern: `tool [global-flags] <command> [flags] [args]`
3. **Global flags** — flags that apply to all commands (--help, --verbose, --config, etc.)
4. **For each command** (infer from exported function names and module names):
   - Syntax: `tool command [flags] <required-arg> [optional-arg]`
   - Description: what it does
   - Flags: table with Flag | Default | Description
   - Example: 1-2 concrete usage examples
5. **Exit codes** — if detectable from the code
6. **Environment variables** — any env vars the CLI reads

Base commands on actual exported function/method names. Mark inferred items clearly.
Language: {language}"""
        return sys, user

    # --- CLI: configuration
    if chapter_file == "06-config.md":
        user = f"""Generate **06-config.md** — the Configuration Reference for **{project_name}**.
{ctx}
## What this document must contain
1. `# Configuration` heading
2. **Configuration sources** — in priority order (CLI flags > env vars > config file > defaults)
3. **Config file** — format (YAML/TOML/JSON/INI), default location, example with all options
4. **Environment variables** — table: Variable | Default | Description
5. **Per-command config** — any command-specific settings
6. **Profiles / environments** — if multiple environments are supported (dev/prod/staging)

Infer from config file names detected and module exports. Language: {language}"""
        return sys, user

    # --- Library: public API
    if chapter_file == "05-api-reference.md" and project_type == "library_sdk":
        user = f"""Generate **05-api-reference.md** — the Public API Reference for the library **{project_name}**.
{ctx}
## What this document must contain
1. `# Public API Reference` heading
2. **Package/module structure** — how the public API is organized
3. **For each public export** (use actual exported names from repo map):
   - Signature with types
   - Description: what it does, when to use it
   - Parameters: table with Name | Type | Required | Description
   - Returns: type and description
   - Example: minimal working code snippet
4. **Error handling** — what exceptions/errors can be raised and when
5. **Deprecation notices** — if any deprecated APIs are detected

Focus on the PUBLIC surface only. Ignore internal/private exports.
Language: {language}"""
        return sys, user

    # --- Library: integration guide
    if chapter_file == "06-integration.md":
        user = f"""Generate **06-integration.md** — the Integration Guide for the library **{project_name}**.
{ctx}
## What this document must contain
1. `# Integration Guide` heading
2. **Installation** — how to add this library as a dependency (pip, npm, cargo, maven, etc.)
3. **Minimal working example** — the simplest possible usage in a code block
4. **Common use cases** — 3-4 typical integration scenarios with code examples
5. **Framework integrations** — if the library works with specific frameworks, show how
6. **Configuration** — any initialization/setup required before using
7. **Testing** — how to mock/stub this library in tests

Language: {language}"""
        return sys, user

    # --- Data science: pipeline
    if chapter_file == "04-data-pipeline.md":
        user = f"""Generate **04-data-pipeline.md** — the Data Pipeline chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# Data Pipeline` heading
2. **Pipeline overview** — Mermaid flowchart showing data flow from source to output
3. **Data sources** — what data comes in (files, databases, APIs, streams)
4. **Transformation steps** — each processing stage with:
   - Input/output format
   - Key transformations applied
   - Relevant code module
5. **Data storage** — where processed data is stored
6. **Scheduling / triggers** — how/when the pipeline runs
7. **Data validation** — any quality checks in the pipeline

Language: {language}"""
        return sys, user

    # --- Data science: models & training
    if chapter_file == "05-models.md":
        user = f"""Generate **05-models.md** — the Models & Training chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# Models & Training` heading
2. **Model overview** — what problem is being solved, what type of model (classification, regression, etc.)
3. **Architecture** — model structure (layers, hyperparameters if visible in code)
4. **Training process**:
   - How to run training (command/script)
   - Key hyperparameters and their defaults
   - Training data format expected
5. **Evaluation** — metrics used, how to evaluate, expected performance
6. **Inference** — how to use a trained model for prediction
7. **Model artifacts** — where models are saved, format, versioning

Language: {language}"""
        return sys, user

    # --- Data science: experiments
    if chapter_file == "06-experiments.md":
        user = f"""Generate **06-experiments.md** — the Experiments chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# Experiments` heading
2. **Experiment tracking** — what tool is used (MLflow, W&B, DVC, custom) if detectable
3. **How to run an experiment** — step by step
4. **Key metrics** — what is being tracked and optimized
5. **Results** — how to view/compare results
6. **Reproducibility** — seeds, environment pinning, data versioning

Language: {language}"""
        return sys, user

    # --- Frontend: components
    if chapter_file == "05-components.md":
        user = f"""Generate **05-components.md** — the Components chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# Components` heading
2. **Component architecture** — how components are organized (atomic design, feature-based, etc.)
3. **For each key component** (use exported component names from repo map):
   - Purpose and when to use it
   - Props/inputs: table with Name | Type | Required | Default | Description
   - Events/outputs emitted
   - Usage example (JSX/template snippet)
4. **Shared/base components** vs **feature components** — how they differ
5. **Styling approach** — CSS modules, Tailwind, styled-components, etc.

Language: {language}"""
        return sys, user

    # --- Frontend: state management
    if chapter_file == "06-state.md":
        user = f"""Generate **06-state.md** — the State Management chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# State Management` heading
2. **State architecture** — global vs local state, what library is used (Redux, Zustand, Pinia, etc.)
3. **Store structure** — how state is organized (slices, modules, stores)
4. **For each store/slice** (from exported names):
   - What state it manages
   - Key actions/mutations
   - How to read from it
5. **Data fetching** — how async data is handled (React Query, SWR, store actions, etc.)
6. **State diagram** — Mermaid diagram of key state transitions if applicable

Language: {language}"""
        return sys, user

    # --- Mobile: screens
    if chapter_file == "05-screens.md":
        user = f"""Generate **05-screens.md** — the Screens & Navigation chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# Screens & Navigation` heading
2. **Navigation structure** — Mermaid diagram of the screen hierarchy/flow
3. **Navigation library** — React Navigation, Expo Router, Flutter Navigator, etc.
4. **For each key screen** (infer from module names like *Screen, *Page, *View):
   - Purpose
   - Route/path
   - Key data displayed
   - Navigation actions (where it can go)
5. **Deep linking** — if detected
6. **Auth flow** — protected routes, login redirect

Language: {language}"""
        return sys, user

    # --- Mobile: native integrations
    if chapter_file == "06-native.md":
        user = f"""Generate **06-native.md** — the Native Integrations chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# Native Integrations` heading
2. **Permissions** — what device permissions are requested and why
3. **Native APIs used** — camera, location, notifications, biometrics, storage, etc.
4. **Push notifications** — setup, payload format, handling
5. **Offline support** — local storage, sync strategy
6. **Platform differences** — iOS vs Android behavior differences if any

Language: {language}"""
        return sys, user

    # --- Desktop: UI & windows
    if chapter_file == "05-ui.md":
        user = f"""Generate **05-ui.md** — the UI & Windows chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# UI & Windows` heading
2. **Window structure** — main window, child windows, dialogs
3. **UI framework** — Electron/React, Qt, GTK, Tauri/Svelte, etc.
4. **Key UI components** — what they do and where they're defined
5. **IPC / communication** — how UI communicates with backend/main process
6. **Theme / styling** — dark mode support, theming system

Language: {language}"""
        return sys, user

    # --- Desktop: platform guide
    if chapter_file == "06-platform.md":
        user = f"""Generate **06-platform.md** — the Platform Guide for **{project_name}**.
{ctx}
## What this document must contain
1. `# Platform Guide` heading
2. **Supported platforms** — Windows / macOS / Linux and their minimum versions
3. **Platform-specific behavior** — things that work differently per OS
4. **Packaging & distribution** — how to build installers/packages per platform
5. **Auto-update** — if implemented, how it works
6. **Native dependencies** — any platform-native requirements

Language: {language}"""
        return sys, user

    # --- Infra: resources
    if chapter_file == "04-resources.md":
        user = f"""Generate **04-resources.md** — the Infrastructure Resources chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# Infrastructure Resources` heading
2. **Resource overview** — Mermaid diagram of all infrastructure components and their relationships
3. **For each resource type** (compute, network, storage, database, etc.):
   - What it is
   - Configuration highlights
   - Key settings to know
4. **Environments** — prod / staging / dev differences
5. **Cost considerations** — which resources drive cost

Language: {language}"""
        return sys, user

    # --- Infra: variables
    if chapter_file == "05-variables.md":
        user = f"""Generate **05-variables.md** — the Variables & Configuration chapter for **{project_name}**.
{ctx}
## What this document must contain
1. `# Variables & Configuration` heading
2. **Input variables** — table: Name | Type | Default | Required | Description
3. **Output values** — what the infra exports for other modules to use
4. **Secrets management** — how sensitive values are handled (vault, SSM, env vars)
5. **Per-environment config** — how to override for different environments
6. **Terraform/Helm/Ansible specifics** — based on what tool is detected

Language: {language}"""
        return sys, user

    # --- Infra: deployment
    if chapter_file == "06-deployment.md":
        user = f"""Generate **06-deployment.md** — the Deployment Guide for **{project_name}**.
{ctx}
## What this document must contain
1. `# Deployment Guide` heading
2. **Prerequisites** — tools needed, access requirements, credentials
3. **First-time setup** — how to initialize/bootstrap from scratch
4. **Deploy to each environment** — step-by-step commands
5. **Rollback procedure** — how to undo a deployment
6. **Drift detection** — how to check if reality matches desired state
7. **CI/CD integration** — how deployments are automated

Language: {language}"""
        return sys, user

    # --- Monorepo: service map
    if chapter_file == "06b-service-map.md":
        user = f"""Generate **06b-service-map.md** — the Service Map for the monorepo **{project_name}**.
{ctx}
## What this document must contain
1. `# Service Map` heading
2. **Service/layer inventory** — table: Service | Language | Purpose | Port/URL
3. **Inter-service communication** — Mermaid diagram of how services call each other
4. **Shared packages** — what code is shared across services and where it lives
5. **Contracts** — API contracts, shared types, event schemas between services
6. **Local development** — how to run all services together (docker-compose, scripts, etc.)
7. **Deployment topology** — how services are deployed together

Language: {language}"""
        return sys, user

    # --- Fallback for unknown chapter files
    user = f"""Generate the documentation chapter **{chapter_file}** for **{project_name}**.
{ctx}
Write a complete, well-structured Markdown document appropriate for this chapter.
Use headers, tables, code blocks, and Mermaid diagrams where helpful.
Language: {language}"""
    return sys, user
