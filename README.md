# ⚒ RepoForge

> AI-powered code analysis tool that generates **technical documentation** and **AI agent skills** from any codebase — works with any LLM.

[![PyPI version](https://img.shields.io/pypi/v/repoforge)](https://pypi.org/project/repoforge/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What it does

RepoForge analyzes your codebase and generates two types of output:

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
- **agent-teams-lite** (skill registry at `.atl/skill-registry.md`)
- **Gentleman-Skills** format (YAML frontmatter, `Trigger:`, `Critical Patterns`)

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
  --theme [vue|dark|buble]  Docsify theme  [default: vue]
  --serve                   Serve docs after generating (opens browser)
  --serve-only              Skip generation, serve existing docs
  --port INT                Server port  [default: 8000]
  --dry-run                 Plan only, no LLM calls, no files written
  -q, --quiet               Suppress progress output
```

### Publish to GitHub Pages

RepoForge can publish docs automatically with GitHub Actions.

1. Add `.github/workflows/docs.yml` to your repository.
2. Set Pages to **Build and deployment: GitHub Actions**.
3. Push to `main`.
4. The workflow runs `repoforge docs`, uploads `docs/`, and deploys to Pages.

After deploy, your docs are available at:

`https://<your-user>.github.io/<your-repo>/`

Manual flow is still supported:

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
  --no-opencode             Skip mirroring to .opencode/
  --serve                   Open skills browser after generating
  --serve-only              Skip generation, open existing skills browser
  --port INT                Server port  [default: 8765]
  --dry-run                 Plan only, no LLM calls
  -q, --quiet               Suppress progress output
```

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
└── SKILLS_INDEX.md

.opencode/                        ← identical mirror
.atl/skill-registry.md            ← agent-teams-lite registry
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
```

---

## Python API

```python
from repoforge import generate_artifacts, generate_docs

# Skills + agents
generate_artifacts(
    working_dir="/path/to/repo",
    output_dir=".claude",
    model="github/gpt-4o-mini",
    also_opencode=True,
)

# Documentation
generate_docs(
    working_dir="/path/to/repo",
    output_dir="docs",
    model="claude-haiku-3-5",
    language="Spanish",
)
```

---

## How it works

```
1. SCAN   (free, no LLM) — detect layers, extract exports/imports, detect stack
2. PLAN   (free, no LLM) — select chapters by project type, rank modules
3. GENERATE (LLM calls)  — one call per chapter or skill
4. WRITE                 — Docsify-ready docs/ or .claude/ skills
```

The LLM only generates **text**. All structural analysis is deterministic.

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

*Inspired by [CodeViewX](https://github.com/dean2021/codeviewx) · Skill format: [Gentleman-Skills](https://github.com/Gentleman-Programming/Gentleman-Skills) · Agent pattern: [agent-teams-lite](https://github.com/Gentleman-Programming/agent-teams-lite)*
