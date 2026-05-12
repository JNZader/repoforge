# RepoForge

AI-powered code analysis for generating technical docs, agent skills, security scans, code graphs, architecture diagrams, and LLM-ready repo exports.

[![PyPI version](https://img.shields.io/pypi/v/repoforge-ai?label=PyPI&color=blue)](https://pypi.org/project/repoforge-ai/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Live Demo](https://repoforge.javierzader.com) · [PyPI](https://pypi.org/project/repoforge-ai/) · [GitHub](https://github.com/JNZader/repoforge) · [Issues](https://github.com/JNZader/repoforge/issues)

Visuals coming soon.

## Quick Portfolio Snapshot

- Turns a codebase into Docsify-ready documentation, multi-agent skill packs, diagrams, and LLM context exports.
- Mixes deterministic analysis with optional LLM text generation instead of pretending the model understands the repo by magic.
- Supports recruiter-friendly demos and serious engineering workflows: local docs preview, GitHub Pages publish, CI checks, compression, scanning, and API usage.
- Works across Python, TypeScript, JavaScript, Go, Java, Kotlin, Rust, Ruby, PHP, and monorepos.

## Why It Matters

RepoForge is useful when you need to:

- onboard engineers into an unfamiliar codebase fast
- generate internal docs without hand-writing every chapter
- create agent instructions for Claude Code, OpenCode, Cursor, Codex, Gemini, and Copilot from one source
- flatten a repository into a single LLM-friendly context file
- audit generated markdown for secrets, prompt injection, or unsafe commands
- understand architectural blast radius before refactoring
- publish a docs site to GitHub Pages without building a custom docs pipeline

## Quick Start

```bash
pip install repoforge-ai

# Generate Docsify-ready docs
repoforge docs -w /path/to/repo --lang English

# Generate multi-tool skills
repoforge skills -w /path/to/repo --targets all

# Export repo context for an LLM
repoforge export -w /path/to/repo -o context.md

# Run deterministic security scanning
repoforge scan -w /path/to/repo
```

Notes:

- CLI command: `repoforge`
- PyPI package name: `repoforge-ai`
- Recommended for speed: install `ripgrep`

## Jump To Technical Docs

- [Technical README](#technical-readme)
- [Command Breakdown](#command-breakdown)
- [`docs` Command](#docs-command)
- [`skills` Command](#skills-command)
- [`repoforgeyaml` Config](#repoforgeyaml--per-repo-config)
- [Python API](#python-api)

---

## Technical README

### Table of Contents

- [What It Does](#what-it-does)
- [Command Breakdown](#command-breakdown)
- [What Changed](#what-changed)
- [Installation](#installation)
- [Model Setup](#model-setup)
- [Technical Quick Start](#technical-quick-start)
- [`docs` Command](#docs-command)
- [`skills` Command](#skills-command)
- [`export` Command](#export-command)
- [`score` Command](#score-command)
- [`scan` Command](#scan-command)
- [`compress` Command](#compress-command)
- [`graph` Command](#graph-command)
- [`diagram` Command](#diagram-command)
- [GitHub Pages Deployment](#github-pages-deployment)
- [Monorepo Support](#monorepo-support)
- [`repoforge.yaml` - Per-Repo Config](#repoforgeyaml--per-repo-config)
- [Python API](#python-api)
- [How It Works](#how-it-works)
- [Cost Estimate](#cost-estimate)
- [Supported Stacks](#supported-stacks)
- [License](#license)
- [Inspirations](#inspirations)

## What It Does

RepoForge analyzes a repository and produces multiple outputs from the same scan.

### 1. `repoforge docs`

Generates a Docsify-ready technical documentation site adapted to project type.

| Project type | Typical chapters |
|---|---|
| Web service | Data Models, API Reference |
| Frontend SPA | Components, State Management |
| CLI tool | Commands, Configuration |
| Data science | Data Pipeline, Models and Training, Experiments |
| Library or SDK | Public API, Integration Guide |
| Mobile app | Screens and Navigation, Native Integrations |
| Infra or DevOps | Resources, Variables, Deployment Guide |
| Monorepo | Global chapters plus per-layer subdocs |

Shared output includes overview, quick start, architecture, core mechanisms, and development guidance. Output is a `docs/` folder ready for local preview or GitHub Pages.

### 2. `repoforge skills`

Generates `SKILL.md` and `AGENT.md` artifacts for:

- Claude Code in `.claude/skills/` and `.claude/agents/`
- OpenCode in `.opencode/`
- Cursor in `.cursor/rules/*.mdc`
- Codex in `AGENTS.md`
- Gemini CLI in `GEMINI.md`
- GitHub Copilot in `.github/copilot-instructions.md`
- agent-teams-lite registry output in `.atl/skill-registry.md`

### 3. Deterministic analysis commands

No API key required for these:

- `repoforge export` for single-file LLM context
- `repoforge score` for skill quality scoring
- `repoforge scan` for markdown security scanning
- `repoforge compress` for token reduction
- `repoforge graph` for dependency graphs and blast radius
- `repoforge diagram` for Mermaid, SVG, ERD, Kubernetes, and OpenAPI diagrams

## Command Breakdown

### Core commands

| Command | What it does | API key |
|---|---|---|
| `repoforge docs` | Generate Docsify-ready technical documentation | Required for prose generation |
| `repoforge skills` | Generate skills and agents for coding tools | Required for skill generation |
| `repoforge export` | Flatten repo into one LLM-optimized file | No |
| `repoforge score` | Score generated `SKILL.md` files across 7 dimensions | No |
| `repoforge scan` | Scan generated output for security issues | No |
| `repoforge compress` | Compress markdown for lower token cost | No |
| `repoforge graph` | Build dependency graphs and blast-radius views | No |
| `repoforge diagram` | Generate architecture and spec diagrams | No |

### Additional commands in the current CLI

The current CLI also includes `check`, `diff`, `prompts`, `skills-from-docs`, `import-docs`, `validate-skills`, `blast-radius`, `change-impact`, `co-change`, `ownership`, `analyze`, `search`, `slice`, `decisions`, and `registry`.

### Common flags

- `-w`, `--working-dir` or `--workspace`: repo path
- `-o`, `--output`: output file or directory
- `--model`: LLM model
- `--dry-run`: plan only, no LLM calls
- `-q`, `--quiet`: quieter output

## What Changed

### What's New in v0.4

| Feature | Command or flag | Why it matters |
|---|---|---|
| Mermaid diagrams | `repoforge diagram` | Architecture output without hand-drawing diagrams |
| Symbol-level mapping | internal graph and symbols pipeline | Better call graph and structure analysis |
| Incremental docs | `repoforge docs --incremental` | Regenerate only stale chapters using git diff and manifest tracking |
| Dependency health | docs pipeline enrichment | Detect duplicates, license conflicts, transitive depth, outdated deps |
| Coverage unification | docs pipeline enrichment | Parse Cobertura, LCOV, coverage.py JSON, and JaCoCo into one report |

### Previous v0.3 context

Still useful for understanding the project direction:

| Feature | Command or flag | Notes |
|---|---|---|
| LLM export | `repoforge export` | Markdown or XML single-file repo view |
| Complexity routing | `--complexity auto|small|medium|large` | Generation depth adapts to repo size |
| Hooks generation | `--with-hooks` | Recommended Claude Code hooks output |
| Quality scorer | `repoforge score` | Deterministic quality gates for skills |
| Multi-tool targets | `--targets claude,cursor,codex,...` | One source, many agent consumers |
| Progressive disclosure | `--disclosure tiered|full` | Tier markers plus `DISCOVERY_INDEX.md` |
| Token compression | `repoforge compress` | Lower prompt cost without deleting meaning |
| Security scanner | `repoforge scan` | 37 rules across 5 categories |
| Plugin hierarchy | `--plugin` | `plugin.json` and `commands/` generation |
| Code graph | `repoforge graph` | Dependency graph and blast-radius analysis |

## Installation

```bash
pip install repoforge-ai
```

Notes:

- The executable is `repoforge`.
- The PyPI name is `repoforge-ai` because `repoforge` was already taken.
- `ripgrep` is strongly recommended for faster scanning.

```bash
brew install ripgrep
sudo apt install ripgrep
scoop install ripgrep
```

## Model Setup

RepoForge auto-detects providers from environment variables, but explicit setup matters because provider behavior is NOT the same.

### GitHub Models

Best low-friction option if you already use GitHub tooling.

```bash
export GITHUB_TOKEN=$(gh auth token)
repoforge docs -w . --model github/gpt-4o-mini
```

For GitHub Actions, the built-in `GITHUB_TOKEN` is not enough for GitHub Models. You need a PAT with `models:read` scope, usually stored as `GH_MODELS_TOKEN`.

### Groq

```bash
export GROQ_API_KEY=gsk_...
repoforge docs -w . --model groq/llama-3.3-70b-versatile
```

### Ollama

```bash
ollama pull qwen2.5-coder:14b
repoforge docs -w . --model ollama/qwen2.5-coder:14b
```

### Claude Haiku

```bash
export ANTHROPIC_API_KEY=sk-ant-...
repoforge docs -w . --model claude-haiku-3-5
```

### OpenAI

```bash
export OPENAI_API_KEY=sk-...
repoforge docs -w . --model gpt-4o-mini
```

### Practical model notes

- `github/gpt-4o-mini`: easiest default for docs and skills if you already use GitHub
- `claude-haiku-3-5`: cheap and usually good enough for generation
- `ollama/...`: local and free, but quality depends heavily on the model you pull
- `groq/...`: fast and free-tier friendly, but rate limits matter
- `gpt-4o-mini`: solid baseline if you already have OpenAI wired in

## Technical Quick Start

```bash
# Docs
repoforge docs -w /path/to/repo --lang English -o docs

# Serve docs locally
repoforge docs -w . --serve

# Generate skills for Claude + OpenCode + Cursor + Codex
repoforge skills -w /path/to/repo --targets claude,opencode,cursor,codex

# Generate skills and immediately score, scan, and compress them
repoforge skills -w /path/to/repo --score --scan --compress

# Export repo context
repoforge export -w /path/to/repo -o context.md

# Build dependency graph
repoforge graph -w /path/to/repo --format mermaid

# Generate dependency diagram
repoforge diagram -w /path/to/repo --type dependency

# Incremental docs
repoforge docs -w /path/to/repo --incremental

# Plan only
repoforge docs -w /path/to/repo --dry-run
repoforge skills -w /path/to/repo --dry-run
```

## `docs` Command

```text
repoforge docs [OPTIONS]

  -w, --working-dir DIR     Repo to analyze  [default: .]
  -o, --output-dir DIR      Output directory  [default: docs]
  --model TEXT              LLM model
  --lang LANGUAGE           Documentation language  [default: English]
  --name TEXT               Project name override
  --complexity LEVEL        auto|small|medium|large
  --theme THEME             vue|dark|buble|pure
  --serve                   Generate and open local docs
  --serve-only              Skip generation, serve existing docs
  --port INT                Local server port  [default: 8000]
  --chunked                 Use chunked generation mode
  --verify / --no-verify    Enable or disable Stage C verification
  --verify-model TEXT       Verification model override
  --no-verify-docs          Disable verification and deterministic corrections
  --facts-only              Emit factual extraction without prose
  --incremental             Regenerate only stale chapters
  --semantic-dedup          Skip semantically unchanged chapters in incremental mode
  --semantic-threshold FLOAT
  --watch                   Regenerate docs when files change
  --watch-interval FLOAT
  --link-style STYLE        backtick|wiki
  --diagrams                Embed Mermaid diagrams in architecture docs
  --max-workers INT         Parallel chapter workers
  --model-heavy TEXT        Heavy-tier model when --model auto
  --model-standard TEXT     Standard-tier model when --model auto
  --model-light TEXT        Light-tier model when --model auto
  --dry-run
  -q, --quiet
```

### Output

Typical generated docs include:

- `index.md`
- `01-overview.md`
- `02-quickstart.md`
- `03-architecture.md`
- `04-core-mechanisms.md`
- `05-data-models.md` when relevant
- `06-api-reference.md` when relevant
- `07-dev-guide.md`
- `index.html`, `_sidebar.md`, and `.nojekyll` for Docsify and GitHub Pages

### Incremental mode

With `--incremental`, RepoForge tracks chapter dependencies in a manifest and uses `git diff` to decide which chapters are stale. That matters on large repos because regenerating everything is just burning tokens for no reason.

`--semantic-dedup` goes one step further by using embedding similarity to skip chapters whose meaning did not materially change, even if files changed.

### Complexity levels

| Level | Behavior |
|---|---|
| `auto` | Detect from file count and layer count |
| `small` | Fewer files, denser per-file coverage |
| `medium` | Balanced depth |
| `large` | More architectural summarization, less file-by-file noise |

### Local preview

```bash
repoforge docs -w . --serve
```

Or serve the generated folder yourself:

```bash
python3 -m http.server 8000 --directory docs
```

### Version pinning for workflows

If you use the GitHub Action, pin a tag instead of `@main`.

```yaml
uses: JNZader/repoforge@v0.2.0
```

That keeps downstream workflows reproducible instead of gambling on whatever changed overnight.

## `skills` Command

```text
repoforge skills [OPTIONS]

  -w, --working-dir DIR     Repo to analyze  [default: .]
  -o, --output-dir DIR      Output directory  [default: .claude]
  --model TEXT              LLM model
  --complexity LEVEL        auto|small|medium|large
  --targets TARGETS         claude|opencode|cursor|codex|gemini|copilot|all
  --disclosure MODE         tiered|full
  --with-hooks              Generate HOOKS.md
  --plugin                  Generate plugin.json + commands/
  --score                   Score skills after generation
  --compress                Compress skills after generation
  --aggressive              Stronger compression mode
  --scan                    Run security scan after generation
  --no-opencode             Skip mirror to .opencode/
  --serve                   Open skills browser
  --serve-only              Open existing skills browser
  --port INT                Browser port  [default: 8765]
  --dry-run
  -q, --quiet
```

### Output targets

| Target | Output | Format |
|---|---|---|
| `claude` | `.claude/skills/`, `.claude/agents/` | `SKILL.md` and `AGENT.md` |
| `opencode` | `.opencode/` | Mirror of Claude output |
| `cursor` | `.cursor/rules/*.mdc` | Cursor rules |
| `codex` | `AGENTS.md` | Consolidated instructions |
| `gemini` | `GEMINI.md` | Gemini CLI instructions |
| `copilot` | `.github/copilot-instructions.md` | Copilot instructions |

### Example layout

```text
.claude/
├── skills/
│   ├── backend/SKILL.md
│   ├── backend/auth/SKILL.md
│   └── frontend/SKILL.md
├── agents/
│   ├── orchestrator/AGENT.md
│   ├── backend-agent/AGENT.md
│   └── frontend-agent/AGENT.md
├── commands/
├── plugin.json
├── HOOKS.md
├── DISCOVERY_INDEX.md
└── SKILLS_INDEX.md
```

### Things worth knowing

- `--targets all` is the fastest way to produce a full multi-agent output set.
- `--disclosure tiered` adds progressive disclosure markers and index files.
- `--score --scan --compress` lets you treat skill generation like a pipeline instead of a one-shot dump.

## `export` Command

Flatten a repo into one LLM-friendly file. No API key required.

```text
repoforge export [OPTIONS]

  -w, --working-dir DIR     Repo to analyze  [default: .]
  -o, --output FILE         Output file, or stdout if omitted
  --max-tokens INT          Token budget cap
  --no-contents             Tree plus definitions only
  --format FORMAT           markdown|xml
  --compress                API-surface-focused export
  -q, --quiet
```

```bash
repoforge export -w .
repoforge export -w . -o context.md
repoforge export -w . --max-tokens 100000
repoforge export -w . --no-contents
repoforge export -w . --format xml
repoforge export -w . --compress
```

## `score` Command

Scores generated skills across 7 dimensions: completeness, clarity, specificity, examples, format, safety, and agent readiness.

```text
repoforge score [OPTIONS]

  -w, --working-dir DIR     Repo root  [default: .]
  -d, --skills-dir DIR      Skills directory override
  --format FORMAT           table|json|markdown
  --min-score FLOAT         Exit 1 if a skill falls below threshold
  -q, --quiet
```

```bash
repoforge score -w .
repoforge score -w . --format json
repoforge score -w . --min-score 0.7
repoforge score -d /path/to/skills
```

## `scan` Command

Security scanner for generated markdown. No API key required.

Rules cover:

- prompt injection
- hardcoded secrets
- PII exposure
- destructive commands
- unsafe code patterns

It is context-aware: anti-pattern examples are downgraded instead of treated as the same thing as production secrets.

```text
repoforge scan [OPTIONS]

  -w, --workspace DIR       Repo root  [default: .]
  --target-dir DIR          Specific directory override
  --format FORMAT           table|json|markdown
  --allowlist IDS           Comma-separated rule IDs
  --fail-on SEVERITY        critical|high|medium|low
  -q, --quiet
```

```bash
repoforge scan -w .
repoforge scan -w . --format json
repoforge scan -w . --fail-on critical
repoforge scan -w . --allowlist SEC-020,SEC-022
repoforge scan --target-dir ./my-skills
```

## `compress` Command

Deterministic markdown compression for lower token cost. No API key required.

Compression passes include whitespace normalization, filler removal, table compaction, code-block cleanup, bullet consolidation, and optional aggressive abbreviation.

```text
repoforge compress [OPTIONS]

  -w, --workspace DIR       Repo root  [default: .]
  --target-dir DIR          Directory override
  --aggressive              Stronger abbreviation mode
  --dry-run                 Show compression stats only
  -q, --quiet
```

```bash
repoforge compress -w .
repoforge compress -w . --aggressive
repoforge compress -w . --dry-run
repoforge compress --target-dir ./my-skills
```

## `graph` Command

Builds a code knowledge graph from repository structure. No API key required.

It supports file-level dependency graphs, symbol-level call graphs, structured graph queries, community detection, and blast radius analysis.

```text
repoforge graph [OPTIONS]

  -w, --workspace DIR       Repo root  [default: .]
  -o, --output FILE         Output file or stdout
  --format FORMAT           mermaid|json|dot|summary
  --type TYPE               deps|calls
  --blast-radius MODULE     Show impact of a module change
  --v2                      Use extractor-based graph builder
  --depth INT               BFS depth for v2 blast radius
  --max-files INT           Max files in blast-radius result
  --include-tests / --no-include-tests
  --query MODE              callers|callees|imports
  --symbol TEXT             Symbol for callers or callees query
  --file PATH               File path for imports query
  --communities             Detect related module clusters
  --incremental             Use file-hash graph caching
  -q, --quiet
```

```bash
repoforge graph -w .
repoforge graph -w . --format mermaid
repoforge graph -w . --format json -o graph.json
repoforge graph -w . --format dot -o graph.dot
repoforge graph -w . --blast-radius repoforge/cli.py
repoforge graph -w . --type calls
repoforge graph --query callers --symbol build_graph
repoforge graph --query imports --file repoforge/cli.py
repoforge graph -w . --communities --format summary
```

## `diagram` Command

Generates architecture diagrams from code or external specs. No API key required.

```text
repoforge diagram [OPTIONS]

  -w, --workspace DIR       Repo root  [default: .]
  -o, --output FILE         Output file or stdout
  --type TYPE               dependency|directory|callflow|erd|k8s|openapi|svg|all
  --max-nodes INT           Dependency diagram node cap
  --max-depth INT           Directory or call-flow depth
  --entry FILE              Entry point for call-flow diagrams
  --input FILE              Required for erd, k8s, and openapi
  -q, --quiet
```

```bash
repoforge diagram -w .
repoforge diagram -w . --type dependency
repoforge diagram -w . --type callflow --entry src/main.py
repoforge diagram -w . --type erd --input schema.sql
repoforge diagram -w . --type k8s --input k8s/deployment.yaml
repoforge diagram -w . --type openapi --input openapi.json
repoforge diagram -w . --type svg -o architecture.svg
repoforge diagram -w . -o diagrams.md
```

There is also a `repoforge diagrams` command that writes a combined markdown file with multiple Mermaid blocks.

## GitHub Pages Deployment

RepoForge ships a docs workflow with safe deploy modes. The default is generate-only. That is the correct default because clobbering an existing Pages site would be amateur-hour behavior.

### Deploy modes

| Mode | Behavior |
|---|---|
| `none` | Generate docs only, do not publish |
| `auto` | If no live site exists, deploy to Pages root; otherwise deploy to a subpath |
| `main` | Force deploy to Pages root |
| `subpath` | Publish under `/<prefix>/` on `gh-pages` while preserving existing files |

### Step-by-step: safe GitHub Pages setup

1. Copy or reuse `.github/workflows/docs.yml` in your repository.
2. Create a GitHub PAT with `models:read` scope.
3. Save that PAT as the repository secret `GH_MODELS_TOKEN`.
4. Decide whether you want generate-only, root deploy, or subpath deploy.
5. If you want publishing, set repository variables:
   - `REPOFORGE_DOCS_DEPLOY_MODE=auto` or `main` or `subpath`
   - `REPOFORGE_DOCS_CONFIRM_DEPLOY=true`
   - optional `REPOFORGE_DOCS_SUBPATH_PREFIX=docs`
6. Check GitHub Pages settings:
   - for `main`: Pages should use GitHub Actions
   - for `subpath`: Pages should deploy from `gh-pages` branch at `/ (root)`
7. Push to `main`, or trigger `workflow_dispatch` with `deploy_mode`, `confirm_deploy`, and `subpath_prefix`.
8. Open the published URL reported by the workflow summary.

### Required Pages settings by mode

| `deploy_mode` | Deployment mechanism | Required Pages setting |
|---|---|---|
| `none` | Generate only | Any |
| `main` | `actions/deploy-pages@v4` | GitHub Actions |
| `subpath` | `peaceiris/actions-gh-pages@v4` with `keep_files` | Deploy from branch `gh-pages` |
| `auto` | Chooses `main` or `subpath` | Must match actual target |

### Example: add docs without breaking an existing Pages site

```bash
gh variable set REPOFORGE_DOCS_DEPLOY_MODE --body "auto" --repo youruser/yourrepo
gh variable set REPOFORGE_DOCS_CONFIRM_DEPLOY --body "true" --repo youruser/yourrepo
gh variable set REPOFORGE_DOCS_SUBPATH_PREFIX --body "docs" --repo youruser/yourrepo
gh secret set GH_MODELS_TOKEN --repo youruser/yourrepo
```

If your repo already serves `https://youruser.github.io/yourrepo/`, auto mode will prefer a preserved subpath deploy when it detects an existing live site.

### Manual Pages flow

Still supported if you do not want the workflow:

```bash
repoforge docs -w . -o docs --lang English
git add docs
git commit -m "docs: generate documentation"
git push
```

Then configure GitHub Pages to serve `/docs` from `main` if that is your chosen model.

## Monorepo Support

RepoForge auto-detects layers and generates hierarchical docs.

```text
docs/
├── index.md
├── 01-overview.md
├── 03-architecture.md
├── 06b-service-map.md
├── frontend/
│   ├── index.md
│   ├── 05-components.md
│   └── 06-state.md
└── backend/
    ├── index.md
    ├── 05-data-models.md
    └── 06-api-reference.md
```

That means you get a global architecture view plus layer-specific chapters instead of one useless, flattened wall of prose.

## `repoforge.yaml` - Per-Repo Config

Create `repoforge.yaml` in the repo root to override defaults.

```yaml
# Core identity
project_name: "My App"
project_type: web_service
language: English

# Model selection
model: github/gpt-4o-mini

# If you want per-tier routing, set model: auto and configure tiers
models:
  heavy: claude-haiku-3-5
  standard: github/gpt-4o-mini
  light: github/gpt-4o-mini

# Generation depth
complexity: auto
disclosure: tiered

# Multi-tool output
targets: [claude, opencode, cursor, codex]
generate_hooks: true
generate_plugin: true

# Monorepo layer overrides
layers:
  frontend: apps/web
  backend: apps/api
  shared: packages/shared

# Docs generation defaults
parallel:
  max_workers: 4

# Optional chapter-level customization
pages:
  - file: "03-architecture.md"
    sections:
      - type: intro
        order: 1
        content: "This project follows a layered architecture."
      - type: diagram
        enabled: true
        order: 2
      - type: custom
        title: "Deployment Notes"
        order: 3
        content: "Production deploys through GitHub Actions."

# Optional project-type template overrides
templates:
  - name: "custom-web-service"
    project_type: web_service
    chapters:
      - file: "08-ops.md"
        title: "Operations"
        description: "Runbooks, observability, and deployment notes"
        prompt_key: dev_guide
        order: 80
```

### Config behavior notes

- CLI flags beat config values.
- If `model` is not `auto`, the same model is used for heavy, standard, and light tiers.
- If `model: auto`, RepoForge reads `models.heavy`, `models.standard`, and `models.light`.
- `targets` can be a YAML list and map directly to multi-tool output.
- `pages` customizes sections within generated chapters.
- `templates` lets you override or extend chapter templates for project types.

## Python API

RepoForge is not just a CLI wrapper. You can call the underlying library directly.

```python
from repoforge import (
    generate_artifacts,
    generate_docs,
    export_llm_view,
    SkillScorer,
    SkillCompressor,
    SecurityScanner,
    scan_generated_output,
    build_graph,
    build_graph_from_workspace,
    build_graph_v2,
    get_blast_radius_v2,
    generate_dependency_diagram,
    generate_directory_diagram,
    generate_call_flow_diagram,
    generate_all_diagrams,
    Manifest,
    ChapterEntry,
    load_manifest,
    save_manifest,
    get_changed_files,
    build_chapter_deps,
    get_stale_chapters,
    DependencyHealthReport,
    analyze_dependency_health,
    CoverageReport,
    auto_detect_and_parse,
    render_coverage_markdown,
    adapt_for_cursor,
    adapt_for_codex,
    adapt_for_gemini,
    adapt_for_copilot,
    resolve_targets,
    ALL_TARGETS,
)

# Generate skills and agents
generate_artifacts(
    working_dir="/path/to/repo",
    output_dir=".claude",
    model="github/gpt-4o-mini",
    targets="claude,cursor,codex",
    complexity="auto",
    with_hooks=True,
    with_plugin=True,
    disclosure="tiered",
    compress=True,
)

# Generate documentation
generate_docs(
    working_dir="/path/to/repo",
    output_dir="docs",
    model="claude-haiku-3-5",
    language="English",
    complexity="auto",
    incremental=True,
    embed_diagrams=True,
)

# Export repo context
context = export_llm_view(
    workspace="/path/to/repo",
    output_path="context.md",
    max_tokens=100000,
    fmt="markdown",
)

# Score skills
scorer = SkillScorer()
scores = scorer.score_directory(".claude/skills")
print(scorer.report(scores, fmt="table"))

# Scan generated output
scan_result = scan_generated_output("/path/to/repo")
scanner = SecurityScanner()
print(scanner.report(scan_result, fmt="table"))

# Graph and blast radius
graph = build_graph_from_workspace("/path/to/repo")
print(graph.to_mermaid())
graph_v2 = build_graph_v2("/path/to/repo")
blast = get_blast_radius_v2(graph_v2, "repoforge/cli.py")

# Diagrams
print(generate_dependency_diagram(graph_v2, max_nodes=40))

# Incremental docs helpers
manifest = load_manifest("docs")
changed = get_changed_files("/path/to/repo")

# Dependency health and coverage
health = analyze_dependency_health("/path/to/repo")
reports = auto_detect_and_parse("/path/to/repo")
markdown = render_coverage_markdown(reports)
```

### API areas worth knowing

- docs generation: `generate_docs`
- skills generation: `generate_artifacts`
- repo export: `export_llm_view`
- scanning and scoring: `SecurityScanner`, `SkillScorer`
- graph analysis: `build_graph_from_workspace`, `build_graph_v2`, `get_blast_radius_v2`
- diagrams: `generate_dependency_diagram`, `generate_all_diagrams`
- incremental docs: manifest and stale-chapter helpers
- adapters: `adapt_for_cursor`, `adapt_for_codex`, `adapt_for_gemini`, `adapt_for_copilot`

## How It Works

```text
1. SCAN     (deterministic)  Detect stack, layers, files, symbols, and structure
2. PLAN     (deterministic)  Choose chapters, rank modules, route by complexity
3. GENERATE (LLM)            Produce prose for docs or skills
4. ADAPT    (deterministic)  Convert output to Cursor, Codex, Gemini, Copilot, OpenCode formats
5. ENRICH   (deterministic)  Add scans, compression, plugin manifests, diagrams, dependency health, coverage
6. WRITE                     Emit Docsify docs, skills, agents, exports, and reports
```

Important distinction: the LLM generates text, but the structural analysis, graphing, scoring, scanning, coverage parsing, and diagram generation are deterministic.

## Cost Estimate

| Model | Approximate cost for a medium repo |
|---|---|
| GitHub Models | Free with the right token setup |
| Groq | Free tier, rate-limited |
| Ollama | Free local runtime |
| Claude Haiku 3.5 | Around $0.05 |
| GPT-4o-mini | Around $0.04 |
| Claude Sonnet | Around $0.50 |

## Supported Stacks

Language-agnostic, with coverage across Python, TypeScript, JavaScript, Go, Java, Kotlin, Rust, Ruby, PHP, and mixed monorepos.

## License

MIT

## Inspirations

- [CodeViewX](https://github.com/dean2021/codeviewx)
- [Gentleman-Skills](https://github.com/Gentleman-Programming/Gentleman-Skills)
- [agent-teams-lite](https://github.com/Gentleman-Programming/agent-teams-lite)
- [repomix](https://github.com/yamadashy/repomix)
- [rendergit](https://github.com/nicobytes/rendergit)
- [aider](https://github.com/Aider-AI/aider)
- [semgrep](https://github.com/semgrep/semgrep)
