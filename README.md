# ⚒ RepoForge

> AI-powered code analysis tool that generates **technical documentation**, **AI agent skills**, **security scans**, **code graphs**, and **LLM-ready exports** from any codebase — works with any LLM.

[![PyPI version](https://img.shields.io/pypi/v/repoforge-ai)](https://pypi.org/project/repoforge-ai/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What it does

RepoForge analyzes your codebase and generates multiple types of output:

### 1. `repoforge docs` — Technical Documentation

Generates a complete **Docsify-ready** documentation site adapted to your project type:

| Project type | Specific chapters |
|---|---|
| Web service | Data Models · API Reference |
| Frontend SPA | Components · State Management |
| CLI tool | Commands · Configuration |
| Data science | Data Pipeline · Models & Training · Experiments |
| Library/SDK | Public API · Integration Guide |
| Mobile app | Screens & Navigation · Native Integrations |
| Infra/DevOps | Resources · Variables · Deployment Guide |
| **Monorepo** | Global chapters + **per-layer subdocs** (each layer gets its own set) |

All types share: Overview · Quick Start · Architecture · Core Mechanisms · Dev Guide

Output is a `docs/` folder ready for **GitHub Pages** — zero extra config.

### 2. `repoforge skills` — AI Agent Skills

Generates `SKILL.md` and `AGENT.md` compatible with:
- **Claude Code** (`.claude/skills/`, `.claude/agents/`)
- **OpenCode** (mirrored to `.opencode/`)
- **Cursor** (`.cursor/rules/*.mdc`)
- **Codex** (`AGENTS.md`)
- **Gemini CLI** (`GEMINI.md`)
- **GitHub Copilot** (`.github/copilot-instructions.md`)
- **agent-teams-lite** (skill registry at `.atl/skill-registry.md`)
- **Gentleman-Skills** format (YAML frontmatter, `Trigger:`, `Critical Patterns`)

---

## What's New in v0.3

| # | Feature | Command / Flag | Description |
|---|---------|---------------|-------------|
| 1 | **LLM Export** | `repoforge export` | Flatten repo into single LLM-optimized file (markdown or XML) |
| 2 | **Complexity routing** | `--complexity auto\|small\|medium\|large` | Auto-routes generation depth by repo size |
| 3 | **Hooks generation** | `--with-hooks` | Generates HOOKS.md with recommended Claude Code hooks |
| 4 | **Quality scorer** | `repoforge score` | Standalone scorer with 7 dimensions (no API key) |
| 5 | **Multi-tool targets** | `--targets claude,cursor,codex,...` | Generate for 6 AI tools at once |
| 6 | **Progressive disclosure** | `--disclosure tiered\|full` | L1/L2/L3 tier markers + DISCOVERY_INDEX.md |
| 7 | **Token compressor** | `repoforge compress` | Reduce token count by 50-75% (no API key) |
| 8 | **Security scanner** | `repoforge scan` | 37 rules in 5 categories (no API key) |
| 9 | **Plugin hierarchy** | `--plugin` | Generates plugin.json + commands/ directory |
| 10 | **Code graph** | `repoforge graph` | Dependency graph with blast radius analysis |

---

## Installation

```bash
pip install repoforge-ai
```

> **Note:** The CLI command is still `repoforge` after installation.
> The PyPI package name is `repoforge-ai` (the name `repoforge` was already taken).

**Recommended:** install [ripgrep](https://github.com/BurntSushi/ripgrep) for 10-100x faster scanning:
```bash
brew install ripgrep          # macOS
sudo apt install ripgrep      # Ubuntu/Debian
scoop install ripgrep         # Windows
```

---

## Quick start

```bash
# Generate docs (auto-detects language, Docsify-ready)
repoforge docs -w /path/to/repo --lang Spanish -o docs

# Preview locally (opens browser automatically)
repoforge docs -w . --serve

# Generate SKILL.md + AGENT.md for Claude Code
repoforge skills -w /path/to/repo

# Generate for ALL AI tools at once
repoforge skills -w /path/to/repo --targets all

# Generate + score + scan + compress in one shot
repoforge skills -w /path/to/repo --score --scan --compress

# Flatten repo for LLM context
repoforge export -w /path/to/repo -o context.md

# Build dependency graph
repoforge graph -w /path/to/repo --format mermaid

# Open skills browser
repoforge skills --serve-only

# See what would be generated (no LLM calls, free)
repoforge docs --dry-run
repoforge skills --dry-run
```

---

## Model setup

RepoForge auto-detects your API key from env vars and picks the best available model.

### GitHub Models — free with GitHub Copilot ⭐
```bash
export GITHUB_TOKEN=$(gh auth token)
repoforge docs -w . --model github/gpt-4o-mini --lang Spanish
```

### Groq — free tier, very fast
```bash
export GROQ_API_KEY=gsk_...
repoforge docs -w . --model groq/llama-3.3-70b-versatile
```

### Ollama — 100% local, free
```bash
ollama pull qwen2.5-coder:14b
repoforge docs -w . --model ollama/qwen2.5-coder:14b
```

### Claude Haiku — cheap, ~$0.05/run
```bash
export ANTHROPIC_API_KEY=sk-ant-...
repoforge docs -w . --model claude-haiku-3-5
```

### OpenAI
```bash
export OPENAI_API_KEY=sk-...
repoforge docs -w . --model gpt-4o-mini
```

---

## `docs` command

```
repoforge docs [OPTIONS]

  -w, --working-dir DIR     Repo to analyze  [default: .]
  -o, --output-dir DIR      Output directory  [default: docs]
  --model TEXT              LLM model (auto from env if not set)
  --lang LANGUAGE           Documentation language  [default: English]
                            English|Spanish|French|German|Portuguese|
                            Chinese|Japanese|Korean|Russian|Italian|Dutch
  --name TEXT               Project name (auto-detected by default)
  --complexity LEVEL        Override repo complexity  [default: auto]
                            auto|small|medium|large
  --theme [vue|dark|buble]  Docsify theme  [default: vue]
  --serve                   Serve docs after generating (opens browser)
  --serve-only              Skip generation, serve existing docs
  --port INT                Server port  [default: 8000]
  --dry-run                 Plan only, no LLM calls, no files written
  -q, --quiet               Suppress progress output
```

### Complexity levels

| Level | Files | Effect |
|---|---|---|
| `auto` | — | Auto-detected from file count + layer count |
| `small` | ≤20 | Fewer chapters, detailed per-file coverage |
| `medium` | ≤200 | Standard depth (default behavior) |
| `large` | >200 | Concise chapters, more architectural focus |

### Publish to GitHub Pages

RepoForge can publish docs automatically with GitHub Actions.

### Version pinning for workflow stability

When using the RepoForge GitHub Action, pin to a tagged release instead of `@main`:

```yaml
uses: JNZader/repoforge@v0.2.0
```

This keeps consumer workflows stable and reproducible. Update the tag explicitly when you want new behavior.

Safe defaults (recommended):

1. Add `.github/workflows/docs.yml` to your repository.
2. Push to `main`.
3. By default, it runs in `generate-only` mode (`deploy_mode=none`) so it does not touch an existing Pages site.

To enable deploy (explicit opt-in):

1. Set repository variable `REPOFORGE_DOCS_DEPLOY_MODE` to one of:
   - `auto` (if no live site -> deploy root, if live site -> deploy subpath)
   - `main` (force root deploy; may replace existing site)
   - `subpath` (deploy to `/repoforge/` on `gh-pages`, preserving existing files)
2. Set repository variable `REPOFORGE_DOCS_CONFIRM_DEPLOY=true`.
3. Optional: set `REPOFORGE_DOCS_SUBPATH_PREFIX` (default: `repoforge`).

You can also run it manually from Actions (`workflow_dispatch`) with `deploy_mode`, `confirm_deploy`, and `subpath_prefix` inputs.

Note: subpath preservation uses `gh-pages` branch deploy. If your repo uses Pages `build_type=workflow`, the workflow will fall back to generate-only for safety.

Required Pages configuration by deploy mode:

| `deploy_mode` | Deployment mechanism | Required Pages setting |
|---|---|---|
| `none` | Generate only (no publish) | Any |
| `main` | `actions/deploy-pages` (artifact) | **Build and deployment: GitHub Actions** |
| `subpath` | `peaceiris/actions-gh-pages` (branch, `keep_files`) | **Deploy from a branch** → `gh-pages` + `/ (root)` |
| `auto` | Chooses `main` or `subpath` | Must match chosen target (`main` => GitHub Actions, `subpath` => `gh-pages`) |

If `auto` selects `subpath` but Pages is configured as `GitHub Actions`, the subpath branch publish may succeed but not be publicly visible.

After deploy, your docs are available at:

`https://<your-user>.github.io/<your-repo>/`

If deployed in subpath mode:

`https://<your-user>.github.io/<your-repo>/<subpath-prefix>/`

### Example: adding docs to a repo with existing Pages

Your repo already has a live site at `https://youruser.github.io/yourrepo/` and you want to add RepoForge docs without breaking it.

```bash
# 1. Copy the docs workflow to your repo
cp .github/workflows/docs.yml <your-repo>/.github/workflows/docs.yml

# 2. Set repo variables for safe subpath deploy
gh variable set REPOFORGE_DOCS_DEPLOY_MODE --body "auto" --repo youruser/yourrepo
gh variable set REPOFORGE_DOCS_CONFIRM_DEPLOY --body "true" --repo youruser/yourrepo
gh variable set REPOFORGE_DOCS_SUBPATH_PREFIX --body "docs" --repo youruser/yourrepo

# 3. Set Pages source to gh-pages branch (required for subpath mode)
#    Settings → Pages → Build and deployment → Deploy from a branch → gh-pages / (root)

# 4. Add the GH_MODELS_TOKEN secret (PAT with models:read scope)
gh secret set GH_MODELS_TOKEN --repo youruser/yourrepo

# 5. Push and let the workflow run
git add .github/workflows/docs.yml && git commit -m "ci: add repoforge docs" && git push
```

Result:
- Your existing site stays at `https://youruser.github.io/yourrepo/` (unchanged).
- RepoForge docs appear at `https://youruser.github.io/yourrepo/docs/`.

### Manual flow

Still supported if you prefer not to use the workflow:

```bash
repoforge docs -w . -o docs --lang English
git add docs/ && git commit -m "docs: generate documentation"
git push
# Settings → Pages → Source: /docs on main branch
```

---

## `skills` command

```
repoforge skills [OPTIONS]

  -w, --working-dir DIR     Repo to analyze  [default: .]
  -o, --output-dir DIR      Output directory  [default: .claude]
  --model TEXT              LLM model
  --complexity LEVEL        Override repo complexity  [default: auto]
                            auto|small|medium|large
  --targets TARGETS         Comma-separated output targets  [default: claude,opencode]
                            claude|opencode|cursor|codex|gemini|copilot|all
  --disclosure MODE         Skill output mode  [default: tiered]
                            tiered (L1/L2/L3 markers) | full (no markers)
  --with-hooks              Generate HOOKS.md with recommended Claude Code hooks
  --plugin                  Generate plugin.json + commands/ hierarchy
  --score                   After generation, score quality of SKILL.md files
  --compress                After generation, compress skills to reduce tokens
  --aggressive              Use aggressive compression (with --compress)
  --scan                    After generation, run security scanner
  --no-opencode             Skip mirroring to .opencode/
  --serve                   Open skills browser after generating
  --serve-only              Skip generation, open existing skills browser
  --port INT                Server port  [default: 8765]
  --dry-run                 Plan only, no LLM calls
  -q, --quiet               Suppress progress output
```

### Multi-tool output

| Target | Output location | Format |
|---|---|---|
| `claude` | `.claude/skills/`, `.claude/agents/` | SKILL.md + AGENT.md |
| `opencode` | `.opencode/` | Mirror of `.claude/` |
| `cursor` | `.cursor/rules/*.mdc` | Cursor rules format |
| `codex` | `AGENTS.md` (project root) | Single consolidated file |
| `gemini` | `GEMINI.md` (project root) | Gemini CLI instructions |
| `copilot` | `.github/copilot-instructions.md` | Copilot instructions |

### Output layout

```
.claude/
├── skills/
│   ├── backend/
│   │   ├── SKILL.md              ← layer-level skill
│   │   ├── auth/SKILL.md         ← per-module skill
│   │   └── reports/SKILL.md
│   └── frontend/
│       ├── SKILL.md
│       └── useGEELayers/SKILL.md
├── agents/
│   ├── orchestrator/AGENT.md     ← delegate-only orchestrator
│   ├── backend-agent/AGENT.md
│   └── frontend-agent/AGENT.md
├── commands/                     ← (with --plugin)
│   ├── review.md
│   └── deploy.md
├── plugin.json                   ← (with --plugin)
├── HOOKS.md                      ← (with --with-hooks)
├── DISCOVERY_INDEX.md            ← (with --disclosure tiered)
└── SKILLS_INDEX.md

.opencode/                        ← identical mirror
.atl/skill-registry.md            ← agent-teams-lite registry
.cursor/rules/*.mdc               ← (with --targets cursor)
AGENTS.md                         ← (with --targets codex)
GEMINI.md                         ← (with --targets gemini)
.github/copilot-instructions.md   ← (with --targets copilot)
```

---

## `export` command

Flatten a repo into a single LLM-optimized file. **No API key needed.**

```
repoforge export [OPTIONS]

  -w, --working-dir DIR     Repo to analyze  [default: .]
  -o, --output FILE         Output file (default: stdout)
  --max-tokens INT          Token budget limit (prioritizes important files)
  --no-contents             Skip file contents — tree + definitions only
  --format FORMAT           Output format  [default: markdown]
                            markdown|xml (CXML-style)
  -q, --quiet               Suppress progress output
```

```bash
repoforge export -w .                         # print to stdout
repoforge export -w . -o context.md           # save to file
repoforge export -w . --max-tokens 100000     # limit output size
repoforge export -w . --no-contents           # tree + definitions only
repoforge export -w . --format xml            # XML output (CXML-style)
```

---

## `score` command

Score quality of generated SKILL.md files across 7 dimensions. **No API key needed.**

Dimensions: completeness, clarity, specificity, examples, format, safety, agent readiness.

```
repoforge score [OPTIONS]

  -w, --working-dir DIR     Repo to analyze  [default: .]
  -d, --skills-dir DIR      Skills directory  [default: .claude/skills/]
  --format FORMAT           Output format  [default: table]
                            table|json|markdown
  --min-score FLOAT         Minimum score (0.0-1.0). Exit 1 if below.
  -q, --quiet               Suppress progress output
```

```bash
repoforge score -w .                     # score with table output
repoforge score -w . --format json       # JSON output
repoforge score -w . --min-score 0.7     # fail if any skill < 70%
```

---

## `scan` command

Security scanner with 37 rules in 5 categories. **No API key needed.**

Categories: prompt injection, hardcoded secrets, PII exposure, destructive commands, unsafe code patterns.

Context-aware: patterns inside Anti-Patterns sections are downgraded to INFO (not false positives).

```
repoforge scan [OPTIONS]

  -w, --workspace DIR       Repo root  [default: .]
  --target-dir DIR          Specific directory to scan (default: auto-detect)
  --format FORMAT           Output format  [default: table]
                            table|json|markdown
  --allowlist IDS           Comma-separated rule IDs to skip (e.g. SEC-020,SEC-022)
  --fail-on SEVERITY        Exit 1 if findings at or above this level
                            critical|high|medium|low
  -q, --quiet               Suppress progress output
```

```bash
repoforge scan -w .                              # scan with table output
repoforge scan -w . --fail-on critical           # CI gate: fail on critical
repoforge scan -w . --allowlist SEC-020,SEC-022  # skip specific rules
```

---

## `compress` command

Token-optimize generated .md files with deterministic multi-pass compression (50-75% reduction). **No API key needed.**

Passes: whitespace normalization, filler phrase removal, table compaction, code block cleanup, bullet consolidation, abbreviations (aggressive only).

```
repoforge compress [OPTIONS]

  -w, --workspace DIR       Repo root  [default: .]
  --target-dir DIR          Directory to compress  [default: .claude/skills/]
  --aggressive              Use abbreviations (function→fn, configuration→config)
  --dry-run                 Show compression stats without modifying files
  -q, --quiet               Suppress progress output
```

```bash
repoforge compress -w .                       # compress .claude/skills/
repoforge compress -w . --aggressive          # also abbreviate words
repoforge compress -w . --dry-run             # show stats only
```

---

## `graph` command

Build a code knowledge graph from scanner data. **No API key needed.**

Uses import/export name matching — no tree-sitter needed.

```
repoforge graph [OPTIONS]

  -w, --workspace DIR       Repo root  [default: .]
  -o, --output FILE         Output file (default: stdout)
  --format FORMAT           Output format  [default: summary]
                            mermaid|json|dot|summary
  --blast-radius MODULE     Show blast radius for a specific module
  -q, --quiet               Suppress progress output
```

```bash
repoforge graph -w .                              # summary to stdout
repoforge graph -w . --format mermaid             # Mermaid diagram
repoforge graph -w . --format json -o graph.json  # D3/Cytoscape-compatible
repoforge graph -w . --blast-radius src/auth.py   # who breaks if auth changes?
```

---

## Monorepo support

Auto-detects layers from directory structure. Docs are generated hierarchically:

```
docs/
├── index.md              ← monorepo home + layer links
├── 01-overview.md        ← global tech stack, all layers
├── 03-architecture.md    ← how layers interact + Mermaid diagram
├── 06b-service-map.md    ← inter-service contracts
├── frontend/             ← classified as frontend_app
│   ├── index.md
│   ├── 05-components.md
│   └── 06-state.md
└── backend/              ← classified as web_service
    ├── index.md
    ├── 05-data-models.md
    └── 06-api-reference.md
```

---

## `repoforge.yaml` — per-repo config

```yaml
# repoforge.yaml (place in repo root)

# Override project name (default: from package.json / pyproject.toml)
project_name: "My App"

# Force project type (default: auto-detected)
# web_service | frontend_app | cli_tool | library_sdk | data_science
# mobile_app | desktop_app | infra_devops | monorepo | generic
project_type: web_service

# Override layer detection (default: auto from directory names)
layers:
  frontend: apps/web
  backend: apps/api
  shared: packages/shared

# Default language for docs
language: Spanish

# Default model
model: github/gpt-4o-mini

# Override auto-detected complexity (affects generation depth)
# auto | small | medium | large
complexity: auto

# Output targets for multi-tool support
# Default: [claude, opencode]
# Valid: claude, opencode, cursor, codex, gemini, copilot
targets: [claude, opencode]

# Generate HOOKS.md with recommended Claude Code hooks
generate_hooks: false

# Generate plugin.json + commands/ hierarchy
generate_plugin: false
```

---

## Python API

```python
from repoforge import (
    # Skills + agents
    generate_artifacts,
    # Documentation
    generate_docs,
    # LLM export
    export_llm_view,
    # Quality scoring
    SkillScorer, SkillScore,
    # Multi-tool adapters
    adapt_for_cursor, adapt_for_codex, adapt_for_gemini, adapt_for_copilot,
    resolve_targets, ALL_TARGETS,
    # Progressive disclosure
    extract_tier, build_discovery_index, estimate_tokens,
    # Token compression
    SkillCompressor, CompressionResult, compress_file, compress_directory,
    # Security scanning
    SecurityScanner, ScanResult, Finding, Severity, scan_generated_output,
    # Plugin hierarchy
    Command, PluginManifest, build_commands, build_plugin_manifest,
    manifest_to_json, manifest_to_markdown, write_plugin,
    # Code graph
    CodeGraph, Node, Edge, build_graph, build_graph_from_workspace,
)

# Skills + agents
generate_artifacts(
    working_dir="/path/to/repo",
    output_dir=".claude",
    model="github/gpt-4o-mini",
    also_opencode=True,
    complexity="auto",
    with_hooks=True,
    with_plugin=True,
    targets="claude,cursor,codex",
    disclosure="tiered",
    compress=True,
)

# Documentation
generate_docs(
    working_dir="/path/to/repo",
    output_dir="docs",
    model="claude-haiku-3-5",
    language="Spanish",
    complexity="auto",
)

# LLM export (no API key needed)
result = export_llm_view(
    workspace="/path/to/repo",
    output_path="context.md",
    max_tokens=100000,
    fmt="markdown",
)

# Quality scoring (no API key needed)
scorer = SkillScorer()
scores = scorer.score_directory(".claude/skills")
print(scorer.report(scores, fmt="table"))

# Security scanning (no API key needed)
scan_result = scan_generated_output("/path/to/repo")
scanner = SecurityScanner()
print(scanner.report(scan_result, fmt="table"))

# Code graph (no API key needed)
graph = build_graph_from_workspace("/path/to/repo")
print(graph.to_mermaid())
print(graph.summary())
affected = graph.get_blast_radius("src/auth.py")
```

---

## How it works

```
1. SCAN     (free, no LLM) — detect layers, extract exports/imports, detect stack
2. PLAN     (free, no LLM) — select chapters by project type, rank modules, route by complexity
3. GENERATE (LLM calls)    — one call per chapter or skill
4. ADAPT    (free, no LLM) — convert to target formats (Cursor, Codex, Gemini, Copilot)
5. ENRICH   (free, no LLM) — hooks, plugin manifest, disclosure index, compression, security scan
6. WRITE                   — Docsify-ready docs/ or .claude/ skills + multi-tool output
```

The LLM only generates **text**. All structural analysis, scoring, compression, scanning, and graph building is deterministic.

---

## Cost estimate

| Model | ~cost for medium repo |
|---|---|
| GitHub Models (Copilot) | **free** |
| Groq | **free** (rate-limited) |
| Ollama (local) | **free** |
| Claude Haiku 3.5 | ~$0.05 |
| GPT-4o-mini | ~$0.04 |
| Claude Sonnet | ~$0.50 |

---

## Supported stacks

Language-agnostic — tested with Python, TypeScript, JavaScript, Go, Java, Kotlin, Rust, Ruby, PHP, and any monorepo combination.

---

## License

MIT

---

## v0.3.0 Inspirations

- [CodeViewX](https://github.com/dean2021/codeviewx) — original export concept
- [Gentleman-Skills](https://github.com/Gentleman-Programming/Gentleman-Skills) — skill format spec
- [agent-teams-lite](https://github.com/Gentleman-Programming/agent-teams-lite) — agent orchestration pattern
- [repomix](https://github.com/yamadashy/repomix) / [rendergit](https://github.com/nicobytes/rendergit) — LLM export and XML format inspiration
- [aider](https://github.com/Aider-AI/aider) — RepoMap-based code graph approach
- [semgrep](https://github.com/semgrep/semgrep) — security scanning rule categories
