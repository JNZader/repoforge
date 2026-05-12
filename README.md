<div align="center">

# ⚒️ RepoForge

**AI-powered code analysis that generates documentation, skills, security scans, code graphs, and LLM-ready exports from any codebase.**

[![PyPI version](https://img.shields.io/pypi/v/repoforge-ai?label=PyPI&color=blue)](https://pypi.org/project/repoforge-ai/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Live Demo](https://repoforge.javierzader.com) · [PyPI](https://pypi.org/project/repoforge-ai/) · [Report Bug](https://github.com/JNZader/repoforge/issues)

<!-- TODO: Add hero image here — a GIF showing repoforge docs generating in terminal -->

</div>

---

<!-- TODO: Add screenshot: CLI generating docs with progress output -->
<!-- TODO: Add screenshot: Generated Docsify documentation site -->
<!-- TODO: Add screenshot: Code graph / Mermaid diagram output -->

## ✨ Features

| | Feature | Description |
|---|---------|-------------|
| 📖 | **Documentation Generator** | Docsify-ready docs adapted to your project type (web, CLI, mobile, infra, monorepo…) |
| 🤖 | **AI Skills Generator** | SKILL.md + AGENT.md for Claude, Cursor, Codex, Gemini, Copilot, and OpenCode |
| 🔒 | **Security Scanner** | 37 rules across 5 categories — prompt injection, secrets, PII, destructive cmds, unsafe patterns |
| 🔗 | **Code Graph** | Dependency graph with blast radius analysis — find what breaks before it does |
| 📊 | **Mermaid Diagrams** | Module dependency, directory structure, and call-flow diagrams from code analysis |
| 📦 | **LLM Export** | Flatten any repo into a single LLM-optimized file (markdown or XML) |
| 💯 | **Quality Scorer** | 7-dimension quality scoring for generated skills |
| 🗜️ | **Token Compressor** | 50-75% token reduction with deterministic multi-pass compression |
| 🔄 | **Incremental Docs** | Only regenerate stale chapters via git diff + manifest tracking |
| 🏥 | **Dependency Health** | Tree depth, transitive deps, duplicates, license conflicts, health scores |
| 🧪 | **Coverage Unification** | Parse Cobertura, lcov, coverage.py, JaCoCo into unified reports |

---

## 🚀 Quick Start

```bash
pip install repoforge-ai
```

```bash
# Generate documentation (auto-detects language, Docsify-ready)
repoforge docs -w /path/to/repo --lang Spanish

# Generate AI skills for all tools at once
repoforge skills -w /path/to/repo --targets all

# Preview docs locally (opens browser)
repoforge docs -w . --serve

# Flatten repo for LLM context (no API key needed)
repoforge export -w . -o context.md

# Security scan (no API key needed)
repoforge scan -w .
```

> 💡 **The CLI command is `repoforge`** — the PyPI package name is `repoforge-ai` (`repoforge` was taken).

> ⚡ Install [ripgrep](https://github.com/BurntSushi/ripgrep) for 10-100x faster scanning:
> `brew install ripgrep` · `apt install ripgrep` · `scoop install ripgrep`

---

## 🌐 Live Demo

Try RepoForge without installing anything:

**[repoforge.javierzader.com](https://repoforge.javierzader.com)**

<!-- TODO: Add screenshot of the live demo web interface -->

---

## 🛠️ Tech Stack

| Category | Technology |
|----------|-----------|
| Language | Python 3.10+ |
| LLM Integration | Claude, GPT, Ollama, Groq, GitHub Models (via LiteLLM) |
| CLI Framework | Click |
| Code Analysis | AST parsing, regex symbol extraction, import/export graph |
| Parsing | Tree-sitter (optional), ripgrep (recommended) |
| Security | 37-rule pattern engine (no external deps) |
| Docs Output | Docsify (GitHub Pages ready) |
| Skills Output | Claude, Cursor, Codex, Gemini, Copilot, OpenCode formats |
| Graph Output | Mermaid, JSON (D3/Cytoscape), DOT, text summary |
| CI/CD | GitHub Actions workflow included |
| Distribution | PyPI (`repoforge-ai`) |

---

## 📋 CLI Commands

| Command | What it does | API Key? |
|---------|-------------|----------|
| `repoforge docs` | Generate Docsify-ready documentation site | ✅ Required |
| `repoforge skills` | Generate AI skills for 6+ coding tools | ✅ Required |
| `repoforge export` | Flatten repo into LLM-optimized file | ❌ Free |
| `repoforge scan` | Security scan (37 rules, 5 categories) | ❌ Free |
| `repoforge score` | Quality score across 7 dimensions | ❌ Free |
| `repoforge graph` | Dependency graph + blast radius | ❌ Free |
| `repoforge diagram` | Mermaid architecture diagrams | ❌ Free |
| `repoforge compress` | Token compression (50-75%) | ❌ Free |

**Common flags:** `-w DIR` repo path · `-o DIR` output path · `--model MODEL` LLM model · `--dry-run` plan only · `-q` quiet

---

## 💰 Cost Estimate

| Model | Cost for Medium Repo |
|-------|---------------------|
| GitHub Models (Copilot) | **Free** |
| Groq | **Free** (rate-limited) |
| Ollama (local) | **Free** |
| Claude Haiku 3.5 | ~$0.05 |
| GPT-4o-mini | ~$0.04 |
| Claude Sonnet | ~$0.50 |

---

## 🔌 Model Setup

RepoForge auto-detects API keys from environment variables:

| Provider | Setup | Example |
|----------|-------|---------|
| **GitHub Models** ⭐ | `export GITHUB_TOKEN=$(gh auth token)` | `--model github/gpt-4o-mini` |
| **Groq** | `export GROQ_API_KEY=gsk_...` | `--model groq/llama-3.3-70b-versatile` |
| **Ollama** | `ollama pull qwen2.5-coder:14b` | `--model ollama/qwen2.5-coder:14b` |
| **Claude** | `export ANTHROPIC_API_KEY=sk-ant-...` | `--model claude-haiku-3-5` |
| **OpenAI** | `export OPENAI_API_KEY=sk-...` | `--model gpt-4o-mini` |

---

## ⚙️ How It Works

```
1. SCAN     (free) — detect layers, extract exports/imports, detect stack, extract symbols
2. PLAN     (free) — select chapters by project type, rank modules, route by complexity
3. GENERATE (LLM)  — one call per chapter or skill (incremental: skip unchanged)
4. ADAPT    (free) — convert to Cursor, Codex, Gemini, Copilot formats
5. ENRICH   (free) — hooks, plugin manifest, security scan, diagrams, compression
6. WRITE    — Docsify-ready docs/ or .claude/ skills + multi-tool output
```

The LLM only generates **text**. All structural analysis, scoring, scanning, graph building, and diagram generation is deterministic.

---

## 🤖 Multi-Tool Skills Output

| Target | Output | Format |
|--------|--------|--------|
| Claude Code | `.claude/skills/` + `.claude/agents/` | SKILL.md + AGENT.md |
| OpenCode | `.opencode/` | Mirror of Claude |
| Cursor | `.cursor/rules/*.mdc` | Cursor rules |
| Codex | `AGENTS.md` | Consolidated |
| Gemini CLI | `GEMINI.md` | Instructions |
| Copilot | `.github/copilot-instructions.md` | Instructions |

---

## 🐍 Python API

```python
from repoforge import generate_docs, generate_artifacts, export_llm_view
from repoforge import SecurityScanner, SkillScorer, build_graph, scan_generated_output

# Generate docs
generate_docs(working_dir="/path/to/repo", language="Spanish")

# Generate skills + agents
generate_artifacts(working_dir="/path/to/repo", targets="claude,cursor,codex")

# LLM export (free, no API key)
export_llm_view(workspace="/path/to/repo", output_path="context.md")

# Security scan (free, no API key)
scan_result = scan_generated_output("/path/to/repo")

# Code graph (free, no API key)
graph = build_graph("/path/to/repo")
print(graph.to_mermaid())
```

---

## ⚙️ Configuration

Create `repoforge.yaml` in your repo root:

```yaml
project_name: "My App"
project_type: web_service     # auto-detected if not set
language: Spanish
model: github/gpt-4o-mini
complexity: auto              # auto|small|medium|large
targets: [claude, opencode]   # AI tool targets
```

Supports monorepos with auto-detected layers and per-layer subdocs. Incremental mode (`--incremental`) only regenerates stale chapters via git diff.

---

## 🚢 GitHub Pages Deployment

RepoForge includes a GitHub Actions workflow for automatic doc deployment:

- **Generate-only** (default): `deploy_mode=none` — safe, no Pages changes
- **Auto**: deploys to root or subpath based on existing site detection
- **Subpath**: preserves existing Pages site, adds docs at `/docs/`

Pin to tagged releases for workflow stability:
```yaml
uses: JNZader/repoforge@v0.2.0
```

See the [docs command reference](#) for full deployment options.

---

## 🌍 Supported Stacks

Language-agnostic — tested with Python, TypeScript, JavaScript, Go, Java, Kotlin, Rust, Ruby, PHP, and any monorepo combination.

---

## 📄 License

MIT

---

## 🙏 Inspirations

- [CodeViewX](https://github.com/dean2021/codeviewx) — export concept
- [Gentleman-Skills](https://github.com/Gentleman-Programming/Gentleman-Skills) — skill format spec
- [agent-teams-lite](https://github.com/Gentleman-Programming/agent-teams-lite) — agent orchestration
- [repomix](https://github.com/yamadashy/repomix) / [rendergit](https://github.com/nicobytes/rendergit) — LLM export & XML format
- [aider](https://github.com/Aider-AI/aider) — RepoMap code graph approach
- [semgrep](https://github.com/semgrep/semgrep) — security rule categories