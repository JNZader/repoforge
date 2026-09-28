---
name: add-graph-context-endpoint
description: >
  Build and format graph context for codebase analysis.
  Trigger: When loading graph_context module for codebase analysis workflows.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: medium
token_estimate: 1200
dependencies: []
related_skills: [build-graph-context, format-api-surface]
load_priority: high
---<!-- L1:START -->
# add-graph-context-endpoint

One sentence: Builds and formats graph context for codebase analysis workflows.

**Trigger**: When loading graph_context module for codebase analysis workflows.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Build graph context | `build_graph_context()` |
| Select code snippets | `select_code_snippets()` |
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Pattern 1: build_graph_context

Builds graph context from root directory and optional file list.

```python
# Real code using actual exported names from this module
context = build_graph_context(root_dir: str, files: list[str] | None=None) -> str
```

### Pattern 2: select_code_snippets

Selects optimal code snippets within token budget.

```python
# Real code using actual exported names from this module
snippets = select_code_snippets(graph, "/path/to/code", entry_points=["main.py"], token_budget=2000)
```

## When to Use

- Analyzing codebase structure for AI context
- Selecting relevant code snippets within token limits
- Building structured graph representations

## Commands

```bash
python -m repoforge.graph_context --help
docker run --rm -v $(pwd):/code repoforge/graph_context:latest
```

## Anti-Patterns

### Don't: Ignore token budget when selecting snippets

```python
# BAD - will exceed context window
snippets = select_code_snippets(graph, root_dir, token_budget=100)  # Too small
```
<!-- L3:END -->