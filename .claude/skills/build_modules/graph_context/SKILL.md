---
name: build-graph-context
description: >
  Generates concise graph‑based context for LLM prompts.
  Trigger: when graph_context is needed for code analysis.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills: [format-api-surface, select-code-snippets]
load_priority: high
---

<!-- L1:START -->
# build-graph-context

Creates a string representation of a code graph for downstream LLM consumption.

**Trigger**: when graph_context is needed for code analysis.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task                     | Pattern |
|--------------------------|---------|
| Full graph context       | `build_graph_context(root, files)` |
| Relevant snippets        | `select_code_snippets(graph, root, entry_points, token_budget)` |
| API surface formatting   | `format_api_surface(root, files, max_tokens)` |

## Critical Patterns (Summary)
- **Build full graph context**: use `build_graph_context` to serialize selected files.
- **Select token‑budgeted snippets**: use `select_code_snippets` with an explicit `token_budget`.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Build full graph context

Serialize a set of source files into a single context string that captures imports, definitions, and relationships.

```python
from repoforge.graph_context import build_graph_context

root_dir = "/app/src"
files = ["module/__init__.py", "module/utils.py"]
graph_context = build_graph_context(root_dir, files)
print(graph_context)
```

### Select token‑budgeted code snippets

Extract the most relevant `CodeSnippet` objects from a `CodeGraph` while respecting a token budget to stay within LLM limits.

```python
from repoforge.graph_context import select_code_snippets

snippets = select_code_snippets(
    graph,                     # CodeGraph instance
    "/app/src",                # root directory
    entry_points=["main.py"], # optional entry points
    token_budget=1500         # keep under LLM token limit
)
for snippet in snippets:
    print(snippet.code)
```

## When to Use

- Generating a complete context for a new module during CI linting.
- Providing focused