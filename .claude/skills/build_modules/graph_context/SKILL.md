---
name: build-graph-context
description: >-
  Build structured graph_context objects for code‑snippet selection.
  Trigger: when a module needs a graph_context for analysis.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills: [select-code-snippets, format-api-surface]
load_priority: high
---

<!-- L1:START -->
# build-graph-context

Create a `graph_context` that aggregates facts, API surface and snippets for downstream tooling.

**Trigger**: when a module needs a `graph_context` for analysis.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task                     | Pattern |
|--------------------------|---------|
| Build full context       | `build_graph_context(...)` |
| Build concise context    | `build_short_graph_context(...)` |
| Pick relevant snippets   | `select_code_snippets(...)` |

## Critical Patterns (Summary)
- **Build Full Graph Context**: use `build_graph_context` (or its variants) to assemble a complete, structured context.
- **Select Relevant Code Snippets**: filter snippets with `select_code_snippets` and the `CodeSnippet` dataclass.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Build Full Graph Context

Assemble facts, API surface and optional module graph into a single `dict` ready for serialization.

```python
from repoforge.graph_context import (
    build_graph_context,
    format_api_surface,
    format_facts_section,
)

def make_context(facts, api):
    # Convert raw API surface and facts to strings
    api_str = format_api_surface(api)
    facts_str = format_facts_section(facts)
    # Build the complete context object
    return build_graph_context(
        facts_section=facts_str,
        api_surface=api_str,
        short=False,          # set True for a concise version
    )
```

### Select Relevant Code Snippets

Leverage `select_code_snippets` to retrieve only the snippets that match a given predicate, returning `CodeSnippet` instances.

```python
from repoforge.graph_context import select_code_snippets, CodeSnippet

def snippets_for_keyword(snippets, keyword):
    # Keep snippets whose code contains the keyword
    return select_code_snippets(
        snippets,
        lambda s: isinstance(s, CodeSnippet) and keyword in s.code,
    )
```

## When to Use

- Generating a complete context for a new module before running static analysis.
- Creating a short context for quick previews in CI pipelines.
- Filtering snippets to feed a language model with only relevant code.

## Commands

```bash
# Build a full graph context via the CLI
python -m repoforge.cli build-graph-context --full

# Build a short context
python -m repoforge.cli build-graph-context --short

# Run inside Docker (image built from the repo)
docker build -t repoforge .
docker run --rm repoforge python -m repoforge.cli build-graph-context
```

## Anti-Patterns

### Don't: Format a graph context without building it first

Formatting raw strings bypasses validation and can produce mismatched sections.

```python
# BAD: manually concatenating strings
raw = "Facts: ..." + "API: ..."
# Missing the structured build step leads to incomplete context
```
<!-- L3:END -->