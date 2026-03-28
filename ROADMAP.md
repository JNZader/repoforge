# Repoforge Master Roadmap — DX-Optimized Implementation Plan

> **Date**: 2026-03-28
> **Based on**: [COMPETITION_ANALYSIS.md](./COMPETITION_ANALYSIS.md) (38 repos, 75 ideas)
> **Total items**: ~93 (75 original + grouped sub-tasks)
> **Estimated effort**: ~70-95 days
> **Target**: v0.2.0 → v1.0.0

---

## Current Architecture Summary

- **`cli.py`** — Click-based CLI: `generate`, `score`, `compare`, `graph`
- **`docs_generator.py`** — Monolithic orchestrator (scan → prompt → OpenAI → markdown)
- **`graph_context.py`** — Dependency graphs via tree-sitter (Python/TS/JS only)
- **`ripgrep.py`** — Code search via ripgrep subprocess
- **`compressor.py`** — Token-based file compression/truncation
- **`docs_prompts.py`** — Prompt templates

**Key constraints**:
- OpenAI is HARDCODED throughout `docs_generator.py`
- No plugin system, no IR layer, no caching, no config file support
- tree-sitter already a dependency but only for import analysis, not chunking
- `score` command exists but is basic (single LLM call)

---

## Dependency Graph

```
Wave 0: Project Hygiene
  │
  ▼
Wave 1: LLM Gateway ◄──────────────────────────────────────┐
  │                                                          │
  ├──────────────┬──────────────┐                            │
  ▼              ▼              ▼                            │
Wave 2:       Wave 5:       Wave 9:                          │
Pipeline+IR   Scoring       Prompts/Persona                  │
  │              │                                           │
  ├──────┐       ▼                                           │
  ▼      ▼    Wave 6: Refinement Loop                        │
Wave 3: Wave 8:                                              │
AST     Output Formats                                       │
  │       │                                                  │
  ▼       ▼                                                  │
Wave 4: Wave 17:                                             │
Caching  Ecosystem                                           │
  │                                                          │
  ├──────────────┬──────────────┐                            │
  ▼              ▼              ▼                            │
Wave 10:      Wave 13:      Wave 14:                         │
CI/CD         Team          Performance ─────────────────────┘
                              │
Wave 7: Knowledge Graph ◄──── (needs Wave 3 + Wave 2)
  │
  ├──────────────┬──────────────┐
  ▼              ▼              ▼
Wave 11:      Wave 12:      Wave 15:
MCP/IDE       Adv Docs      Intelligence
  │
  ▼
Wave 16: UX Polish
  │
  ▼
Wave 18: Enterprise (v1.0)
```

---

## Summary Table

| Wave | Theme | Ideas | Effort | Version | Cumulative Capabilities |
|:----:|-------|:-----:|:------:|:-------:|------------------------|
| 0 | Project Hygiene | 5 | 2-3d | v0.2.0 | CI, tests, logging, config, ignore patterns |
| 1 | LLM Gateway | 6 | 3-5d | v0.3.0 | Any LLM provider, multi-model, token abstraction |
| 2 | Pipeline + IR | 5 | 5-7d | v0.4.0 | Composable pipeline, IR, plugin renderers |
| 3 | AST Intelligence | 5 | 5-7d | v0.5.0 | Code-aware chunking, cross-refs, type extraction, multi-language |
| 4 | Caching | 5 | 4-5d | v0.6.0 | Incremental generation, hash cache, LLM response cache |
| 5 | Quality Scoring | 5 | 4-5d | v0.7.0 | Multi-dimensional scoring, rule-based checks, quality badges |
| 6 | Refinement Loop | 4 | 3-5d | v0.8.0 | Self-improving docs, configurable iteration, section-level refinement |
| 7 | Knowledge Graph | 5 | 5-7d | v0.9.0 | Entity graph, architecture detection, diagrams, semantic search |
| 8 | Output Formats | 5 | 3-4d | v0.10.0 | HTML, PDF, RST, Docusaurus/MkDocs, custom templates |
| 9 | Prompts/Persona | 5 | 3-4d | v0.11.0 | Audience-adaptive, custom prompts, i18n, framework templates |
| 10 | CI/CD Integration | 5 | 3-4d | v0.12.0 | GitHub Action, pre-commit, quality gate, drift detection |
| 11 | MCP & IDE | 5 | 4-5d | v0.13.0 | MCP server, LSP, VS Code extension, watch mode |
| 12 | Advanced Docs | 5 | 4-5d | v0.14.0 | Changelog, API docs, migration guides, onboarding, security |
| 13 | Team Features | 5 | 3-4d | v0.15.0 | Monorepo, style guide, review workflow, ownership, profiles |
| 14 | Performance | 5 | 3-5d | v0.16.0 | Parallel LLM, streaming, rate limiting, cost estimation |
| 15 | Advanced Intelligence | 5 | 5-7d | v0.17.0 | Code examples, dead code, tech debt, complexity, patterns |
| 16 | UX Polish | 5 | 3-4d | v0.18.0 | TUI, progress bars, diff viewer, web dashboard, telemetry |
| 17 | Ecosystem | 5 | 2-3d | v0.19.0 | PyPI extras, Docker, Homebrew, plugin marketplace, self-docs |
| 18 | Enterprise | 5 | 5-7d | v1.0.0 | DAG orchestration, versioned docs, compliance, agentic generation |

---

## Wave 0: Project Hygiene & Developer Foundation (2-3 days)

**Prerequisites**: None
**Ships as**: v0.2.0

Zero-risk improvements that make ALL subsequent development faster and safer.

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 0.1 | CI pipeline: lint, type-check, test on PR | #46 | S | New: `.github/workflows/`, `pyproject.toml` | Every wave (safety net) | Catch regressions before they land |
| 0.2 | Test scaffolding: fixtures, conftest, coverage config | #45 | S | New: `tests/conftest.py`, `pyproject.toml` | Every wave (testability) | Foundation for TDD in all waves |
| 0.3 | Structured logging with verbosity levels | #48 | S | All modules (replace print/bare logging) | Debugging all waves | Debuggable runs, user-friendly output |
| 0.4 | Config file support (`pyproject.toml [tool.repoforge]` + `.repoforge.toml`) | #37, #35 | M | New: `config.py`, modify `cli.py` | Profiles, per-directory config, all CLI features | Users stop repeating flags |
| 0.5 | `.repoignore` / enhanced ignore patterns | #8 | S | `docs_generator.py`, new: `filtering.py` | Better input quality for all generations | Less noise in generated docs |

---

## Wave 1: LLM Provider Abstraction — The Generic Gateway (3-5 days)

**Prerequisites**: Wave 0
**Ships as**: v0.3.0

The **single most important architectural change**. OpenAI is hardcoded. This wave creates a generic LLM gateway supporting ANY OpenAI-compatible endpoint. Designed from day one to connect to a centralized LLM gateway.

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 1.1 | LLM Provider Protocol: abstract interface | #28 (reframed as generic gateway) | M | New: `llm/protocol.py`, `llm/types.py` | ALL LLM-dependent features | Decoupled from any single provider |
| 1.2 | OpenAI provider (refactor existing code) | #28 | M | New: `llm/providers/openai.py`, modify `docs_generator.py` | Proves abstraction works | Zero behavior change, clean architecture |
| 1.3 | Provider registry & config-driven selection | #28 | S | New: `llm/registry.py`, modify `config.py`, `cli.py` | Profiles, model flexibility | `--provider openai --model gpt-4o` |
| 1.4 | OpenAI-compatible generic provider (Ollama, LiteLLM, vLLM, any endpoint) | #28 | S | New: `llm/providers/openai_compat.py` | Offline mode, custom gateways, centralized LLM gateway | One provider covers dozens of backends |
| 1.5 | Anthropic provider | #28 | S | New: `llm/providers/anthropic.py` | Users with Anthropic keys | Multi-vendor support |
| 1.6 | Token counting abstraction (per-provider tokenizer) | #20 | S | New: `llm/tokens.py`, modify `compressor.py` | Accurate budgeting across models | No more OpenAI-specific tiktoken assumption |

**Design sketch**:
```python
# llm/protocol.py
class LLMProvider(Protocol):
    async def complete(self, messages: list[Message], **kwargs) -> CompletionResult: ...
    async def stream(self, messages: list[Message], **kwargs) -> AsyncIterator[StreamChunk]: ...
    def count_tokens(self, text: str) -> int: ...
    def max_context_window(self) -> int: ...
    @property
    def provider_name(self) -> str: ...
    @property
    def model_name(self) -> str: ...
```

The `openai_compat` provider handles ANY endpoint speaking the OpenAI chat completions API. Users just set `base_url` and `api_key`. This IS the centralized gateway connector.

---

## Wave 2: Pipeline Architecture & IR Foundation (5-7 days)

**Prerequisites**: Wave 1
**Ships as**: v0.4.0

Restructures the monolithic `docs_generator.py` into a composable pipeline and introduces the Intermediate Representation that ALL output formats render from.

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 2.1 | Formal IR data model (structured doc representation) | #13 | L | New: `ir/model.py`, `ir/types.py` | ALL output formats, scoring, diffing | Docs are data, not just text |
| 2.2 | Pipeline architecture: Scanner → Analyzer → Generator → Renderer | #13, #14 | L | Refactor `docs_generator.py` → `pipeline/` | ALL pipeline-dependent features | Composable, testable stages |
| 2.3 | Markdown renderer (extract current output logic) | #13 | S | New: `renderers/markdown.py` | Multi-format output | Zero behavior change, clean separation |
| 2.4 | Renderer plugin interface | #13, #14 | M | New: `renderers/protocol.py`, `renderers/registry.py` | All output format ideas | Third-party renderers possible |
| 2.5 | Pipeline hooks/middleware system | #14 | M | New: `pipeline/hooks.py` | Custom pre/post processing | Extensibility without forking |

---

## Wave 3: AST-Aware Intelligence (5-7 days)

**Prerequisites**: Wave 2
**Ships as**: v0.5.0

Upgrades fact extraction from "read whole files" to "understand code structure". tree-sitter is already a dependency — extend its usage.

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 3.1 | AST-aware chunking: split by function/class boundaries | #3 (CRITICAL) | L | New: `chunking/ast_chunker.py`, modify `pipeline/scanner.py` | Better LLM context, token budget, knowledge graph | Dramatically better doc quality |
| 3.2 | Expand tree-sitter language support (Rust, Go, Java, C#, Ruby) | #3 | M | Modify `graph_context.py`, new grammar configs | Broader language support | Not just Python/TS/JS |
| 3.3 | Cross-file reference resolution | #9 | M | Modify `graph_context.py`, new: `analysis/cross_ref.py` | Knowledge graph, architecture inference | Docs show how modules connect |
| 3.4 | Type-aware documentation (extract signatures, generics) | #3 ext | M | New: `analysis/type_extractor.py` | Better API docs | Docs include accurate type info |
| 3.5 | Smart token budgeting per chunk | #20 | M | Modify `compressor.py`, `pipeline/generator.py`, `llm/tokens.py` | Efficient context window use | No more truncation surprises |

---

## Wave 4: Caching & Incremental Generation (4-5 days)

**Prerequisites**: Wave 2 (pipeline), Wave 3 (chunking)
**Ships as**: v0.6.0

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 4.1 | Content hashing: SHA256 per file/chunk | #7, #27, #54 | M | New: `cache/hasher.py`, `cache/store.py` | All incremental features | Foundation for caching |
| 4.2 | Incremental generation: only regenerate changed files | #7 (CRITICAL) | L | Modify `pipeline/scanner.py`, `generator.py`, new: `cache/diff_detector.py` | Fast iteration, CI usage | 10x faster on large repos |
| 4.3 | Dependency-aware cache invalidation | #7 ext | M | Modify `cache/diff_detector.py`, use `graph_context.py` | Correct incremental updates | No stale docs |
| 4.4 | LLM response caching (same input → cached output) | #27 | S | New: `cache/llm_cache.py`, modify `llm/protocol.py` | Cost savings, faster dev | Don't pay twice for same prompt |
| 4.5 | `repoforge status` — show what changed since last generation | #7 ext | S | Modify `cli.py`, use `cache/` | User awareness | Users know what will be regenerated |

---

## Wave 5: Quality & Scoring System (4-5 days)

**Prerequisites**: Wave 2 (IR), Wave 1 (LLM abstraction)
**Ships as**: v0.7.0

The `score` command exists but is basic. This wave makes it a real quality engine powering the refinement loop.

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 5.1 | Multi-dimensional scoring (completeness, accuracy, clarity, freshness) | #5 (CRITICAL) | M | Refactor score → new: `scoring/engine.py`, `scoring/dimensions.py` | Refinement loop, CI gate | Actionable quality metrics |
| 5.2 | Rule-based scoring (no LLM): missing params, empty sections, broken links | #5 | M | New: `scoring/rules.py` | Fast feedback, CI integration | Instant quality check, zero cost |
| 5.3 | Comparative scoring: score against previous version | Part of #4 | S | Modify `cli.py` compare, use `scoring/` | Regression detection | Did docs get better or worse? |
| 5.4 | Quality badges/report generation | #5 ext | S | New: `scoring/report.py` | README integration, CI artifacts | Visible quality in PRs |
| 5.5 | Scoring threshold configuration | #5 ext | S | Modify `config.py`, `scoring/engine.py` | CI gates, refinement stop condition | Configurable quality bar |

---

## Wave 6: Refinement Loop (3-5 days)

**Prerequisites**: Wave 5 (scoring), Wave 1 (LLM abstraction)
**Ships as**: v0.8.0

The #1 critical idea. NEEDS the scoring system from Wave 5 to know when to stop.

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 6.1 | Self-critique loop: generate → score → refine → re-score | #1 (CRITICAL) | L | New: `refinement/loop.py`, `refinement/critic.py`, modify `pipeline/generator.py` | Higher quality output | Docs improve automatically |
| 6.2 | Configurable max iterations + quality threshold stop | #1 | S | Modify `config.py`, `refinement/loop.py` | Cost control | Users control cost vs quality |
| 6.3 | Refinement diff output: show what changed per iteration | #1 ext | S | New: `refinement/diff.py` | User understanding | See exactly how docs improved |
| 6.4 | Section-level refinement (don't regenerate entire doc) | #1 ext | M | Modify `refinement/loop.py`, use IR from Wave 2 | Efficiency | Faster, cheaper refinement |

---

## Wave 7: Knowledge Graph & Architecture Intelligence (5-7 days)

**Prerequisites**: Wave 3 (AST), Wave 2 (pipeline)
**Ships as**: v0.9.0

Three related ideas unified into one coherent knowledge system.

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 7.1 | Knowledge graph construction (entities + relationships) | #6 (CRITICAL), #10 | L | New: `knowledge/graph.py`, `knowledge/entities.py`, use `graph_context.py` | Diagrams, semantic search, architecture docs | Machine-readable codebase understanding |
| 7.2 | Architecture inference (detect MVC, hexagonal, etc.) | #23 | M | New: `knowledge/patterns.py` | Better architectural docs | Auto-detected architecture |
| 7.3 | Architecture diagram generation (Mermaid) | #10 (HIGH) | M | New: `renderers/mermaid.py`, use `knowledge/graph.py` | Visual docs | Auto-generated architecture diagrams |
| 7.4 | Semantic search over knowledge graph | #23 ext | M | New: `knowledge/search.py` | MCP integration, IDE features | Find all modules that handle auth |
| 7.5 | Dependency impact analysis | #6 ext | S | Use `knowledge/graph.py` | Better incremental generation | If I change X, what docs need updating? |

---

## Wave 8: Output Formats & Multi-Format Support (3-4 days)

**Prerequisites**: Wave 2 (IR + renderer plugin system)
**Ships as**: v0.10.0

With the IR in place, adding output formats is straightforward.

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 8.1 | HTML renderer (static site generation) | #15 | M | New: `renderers/html.py` | Static doc sites | Publishable HTML docs |
| 8.2 | PDF renderer | #15 | S | New: `renderers/pdf.py` (via weasyprint) | Print/offline docs | Formal documentation |
| 8.3 | reStructuredText renderer (Sphinx compatible) | #15 | S | New: `renderers/rst.py` | Python ecosystem | Sphinx/ReadTheDocs compatible |
| 8.4 | Docusaurus/MkDocs renderer | #15 | M | New: `renderers/docusaurus.py`, `renderers/mkdocs.py` | Modern doc sites | Popular doc platform support |
| 8.5 | Custom template support (Jinja2) | #15 ext | M | New: `renderers/template.py` | User-defined formats | Full customization |

---

## Wave 9: Prompt Engineering & Persona System (3-4 days)

**Prerequisites**: Wave 1 (LLM abstraction), Wave 2 (pipeline)
**Ships as**: v0.11.0

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 9.1 | Persona/audience-adaptive prompts (beginner, API consumer, contributor, architect) | #11 | M | Refactor `docs_prompts.py` → `prompts/personas.py`, `prompts/templates.py` | Audience-specific docs | Same code, different docs per audience |
| 9.2 | User-defined custom prompt templates | #30 (HIGH) | M | New: `prompts/custom.py`, modify `config.py` | Full prompt control | Users craft their own doc style |
| 9.3 | Few-shot example injection | #11 ext | S | Modify `prompts/templates.py` | Better style consistency | Docs match project voice |
| 9.4 | Language/i18n support for generated docs | #31 | M | New: `prompts/i18n.py`, modify `config.py` | International teams | Docs in Spanish, Portuguese, etc. |
| 9.5 | Framework-specific doc templates (React, Django, FastAPI) | Part of #36 | M | New: `prompts/frameworks/` | Framework-aware generation | Knows about hooks, views, models |

---

## Wave 10: CI/CD & Automation Integration (3-4 days)

**Prerequisites**: Wave 4 (incremental), Wave 5 (scoring)
**Ships as**: v0.12.0

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 10.1 | GitHub Action for doc generation on PR | #16 (HIGH) | M | New: `integrations/github_action/` | CI-driven docs | Auto-docs on every PR |
| 10.2 | Git-aware generation: only process files changed in PR/commit | #16 | M | New: `git/diff_analyzer.py`, modify `pipeline/scanner.py` | Fast CI runs | Only regenerate what changed |
| 10.3 | Pre-commit hook integration | #43 | S | New: `integrations/pre_commit.py`, `.pre-commit-hooks.yaml` | Local automation | Docs checked before commit |
| 10.4 | Doc quality CI gate (fail PR if score below threshold) | #5 + #46 | S | Modify GitHub Action, use `scoring/` | Quality enforcement | Bad docs block merge |
| 10.5 | Doc drift detection in CI | #22 | M | New: `drift/detector.py`, use `cache/` | Doc freshness | Never have stale docs |

---

## Wave 11: MCP & IDE Integration (4-5 days)

**Prerequisites**: Wave 7 (knowledge graph), Wave 1 (LLM abstraction)
**Ships as**: v0.13.0

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 11.1 | MCP server: expose repoforge as tool for AI agents | #2 (CRITICAL), #41 | L | New: `mcp/server.py`, `mcp/tools.py`, `mcp/resources.py` | AI agent integration | Claude/Cursor can call repoforge |
| 11.2 | MCP resources: expose generated docs, knowledge graph | #2 | M | Extend `mcp/resources.py` | AI context enrichment | AI agents read your docs |
| 11.3 | LSP-style features (hover docs, go-to-definition) | #32 | L | New: `lsp/server.py` | IDE integration | Docs in your editor |
| 11.4 | VS Code extension | #32 | L | New: `vscode-extension/` (separate repo) | VS Code users | Generate docs from sidebar |
| 11.5 | Watch mode: auto-regenerate on file change | #38 | M | New: `watch/watcher.py`, use `cache/` | Dev workflow | Real-time doc updates |

---

## Wave 12: Advanced Analysis & Documentation Types (4-5 days)

**Prerequisites**: Wave 3 (AST), Wave 7 (knowledge graph)
**Ships as**: v0.14.0

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 12.1 | Changelog generation from git history | #17 (HIGH) | M | New: `generators/changelog.py`, `git/history.py` | Release automation | Auto-generated changelogs |
| 12.2 | API documentation extraction (REST, GraphQL) | #19 | M | New: `generators/api_docs.py`, `analysis/api_extractor.py` | API consumers | Auto-generated API reference |
| 12.3 | Migration guide generation (between versions) | #26 | M | New: `generators/migration.py` | Version upgrades | Upgrade paths documented |
| 12.4 | Onboarding documentation generation | #25 | M | New: `generators/onboarding.py` | New contributors | Getting started auto-generated |
| 12.5 | Security documentation (threat model, auth flows) | #50 | M | New: `generators/security.py` | Security teams | Auto-generated security docs |

---

## Wave 13: Collaboration & Team Features (3-4 days)

**Prerequisites**: Wave 4 (caching), Wave 5 (scoring)
**Ships as**: v0.15.0

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 13.1 | Multi-repo/monorepo support | #34 (HIGH) | M | Modify `pipeline/scanner.py`, `config.py` | Enterprise usage | Document workspace with 20 packages |
| 13.2 | Team style guide enforcement | #47 | M | New: `style/enforcer.py`, modify `scoring/rules.py` | Consistent team output | Same voice across team |
| 13.3 | Doc review workflow (generate review comments) | #42 | M | New: `integrations/review.py` | PR workflows | AI reviews doc quality in PRs |
| 13.4 | Ownership/CODEOWNERS-aware generation | #55 | S | New: `analysis/ownership.py` | Team context | This module is owned by Team X |
| 13.5 | Config profiles (library, API, CLI, etc.) | #36 (HIGH) | M | Modify `config.py`, new: `profiles/` | Quick setup | `--profile fastapi` just works |

---

## Wave 14: Performance & Scale (3-5 days)

**Prerequisites**: Wave 4 (caching), Wave 1 (LLM abstraction)
**Ships as**: v0.16.0

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 14.1 | Parallel/async LLM calls | #18 (HIGH) | M | Modify `pipeline/generator.py`, `llm/protocol.py` | Speed on large repos | 5-10x faster generation |
| 14.2 | Streaming output (show docs as they generate) | #21 | M | Modify `llm/protocol.py`, `cli.py` | Better UX | Users see progress immediately |
| 14.3 | Rate limiting & retry with backoff | #18 ext | S | New: `llm/rate_limiter.py` | Reliability | No more API failures |
| 14.4 | Memory-efficient processing for large repos | #18 ext | M | Modify `pipeline/scanner.py` | Large repo support | Handle repos with 10k+ files |
| 14.5 | Cost estimation (`--dry-run --estimate-cost`) | #20 ext | S | New: `cost/estimator.py`, modify `cli.py` | Cost control | This will cost ~$2.50 |

---

## Wave 15: Advanced Intelligence Features (5-7 days)

**Prerequisites**: Wave 7 (knowledge graph), Wave 6 (refinement), Wave 3 (AST)
**Ships as**: v0.17.0

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 15.1 | Code example generation (from tests) | #12 (HIGH) | M | New: `generators/examples.py`, `analysis/test_extractor.py` | Better docs | Auto-generated usage examples |
| 15.2 | Dead code / unused export detection | #52 | M | New: `analysis/dead_code.py`, use knowledge graph | Code health | This function is never called |
| 15.3 | Technical debt documentation | #53 | M | New: `generators/tech_debt.py` | Engineering leadership | Auto-documented tech debt |
| 15.4 | Complexity analysis & refactoring suggestions | #51 | M | New: `analysis/complexity.py` | Code health | This function is too complex |
| 15.5 | Design pattern detection & documentation | #23 ext | M | Modify `knowledge/patterns.py` | Architecture understanding | Uses Observer pattern here |

---

## Wave 16: Interactive & UX Polish (3-4 days)

**Prerequisites**: Wave 2 (pipeline), Wave 1 (LLM abstraction)
**Ships as**: v0.18.0

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 16.1 | Interactive mode (TUI with rich/textual) | #29 (HIGH) | M | New: `tui/app.py`, `tui/views.py` | Better UX | Visual doc generation |
| 16.2 | Progress reporting (rich progress bars) | #48 | S | Modify `cli.py`, `pipeline/` | UX polish | Users see what is happening |
| 16.3 | Diff viewer: show changes between doc versions | #4 | M | Modify `cli.py`, new: `diff/viewer.py` | Version comparison | Side-by-side doc diffs |
| 16.4 | Web dashboard for doc status | #29 ext | L | New: `web/` (FastAPI + htmx) | Enterprise UX | Visual dashboard |
| 16.5 | Telemetry & usage analytics (opt-in) | #33 | M | New: `telemetry/`, modify `cli.py` | Product decisions | Understand usage patterns |

---

## Wave 17: Ecosystem & Distribution (2-3 days)

**Prerequisites**: Wave 8 (multi-format), Wave 11 (MCP)
**Ships as**: v0.19.0

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 17.1 | PyPI distribution with extras (`pip install repoforge[all]`) | #39 | S | Modify `pyproject.toml` | Adoption | Easy installation |
| 17.2 | Docker image | #40 | S | New: `Dockerfile`, `docker-compose.yml` | CI/CD integration | Run anywhere |
| 17.3 | Homebrew formula | #39 ext | S | New: `Formula/repoforge.rb` | macOS users | `brew install repoforge` |
| 17.4 | Plugin marketplace / registry | #14 ext | M | New: `plugins/registry.py`, docs | Community extensions | Third-party renderers, analyzers |
| 17.5 | Documentation site for repoforge itself (dogfooding) | #44 | S | New: `docs/` generated by repoforge | Credibility | Eat your own dog food |

---

## Wave 18: Enterprise & v1.0 (5-7 days)

**Prerequisites**: Wave 13 (team), Wave 14 (performance)
**Ships as**: v1.0.0

| # | Idea (grouped) | Original IDs | Complexity | Files Affected | Unblocks | Value |
|---|----------------|-------------|-----------|----------------|----------|-------|
| 18.1 | DAG-based orchestration (complex multi-step pipelines) | #49 | L | New: `orchestration/dag.py` | Complex workflows | Multi-step doc pipelines |
| 18.2 | Context window management (auto model selection by size) | #20 ext | M | Modify `llm/`, `pipeline/generator.py` | Smart model usage | Cheap model for small, expensive for complex |
| 18.3 | Versioned documentation (per git tag/branch) | #56 | M | New: `versioning/manager.py` | Library maintainers | Docs per version |
| 18.4 | Compliance documentation (SOC2, GDPR, HIPAA) | #57 | L | New: `generators/compliance.py` | Enterprise | Auto-generated compliance docs |
| 18.5 | Agentic multi-pass generation (plan → draft → review → finalize) | #58 | XL | New: `agents/planner.py`, `agents/reviewer.py` | State of the art | AI agent-driven doc generation |

---

## Remaining Ideas (mapped or deferred)

| Original ID | Idea | Status |
|------------|-------|--------|
| #24 | Benchmark suite | Covered in Wave 0 (test scaffolding) + Wave 5 (scoring) |
| #35 | Per-directory config | Covered in Wave 0.4 (config file) |
| #59-75 | Various low-priority (comment extraction, README gen, glossary, etc.) | Post-v1.0 backlog |

---

## Key Architectural Decisions

1. **LLM Gateway in Wave 1** — nearly everything downstream benefits from provider flexibility. It's NOT "add Ollama" — it's the generic protocol that a centralized gateway plugs into via the `openai_compat` provider.

2. **Pipeline + IR in Wave 2** — the monolithic `docs_generator.py` is the biggest bottleneck. Until decomposed, you cannot add renderers, hooks, or scoring stages cleanly.

3. **AST chunking in Wave 3** (not Wave 1) — needs the pipeline to exist first. The pipeline gives AST chunks a clean stage to plug into.

4. **Scoring before Refinement** (Wave 5 before 6) — the refinement loop is useless without a stop condition. The scoring system IS the stop condition.

5. **Knowledge Graph in Wave 7** — depends on both AST analysis (Wave 3) and pipeline (Wave 2). Heavy lift but unlocks three waves downstream (MCP, advanced docs, intelligence).

---

> **Generated from**: COMPETITION_ANALYSIS.md (38 repos, 75 ideas)
> **Organizing principle**: Fix what's broken → build foundations → add features → expand reach → polish → enterprise
