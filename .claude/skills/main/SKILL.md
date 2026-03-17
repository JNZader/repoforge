---
name: main-layer
description: >
  This layer owns the core functionality of the project, including evaluation and adaptation modules.
  Trigger: When working in main/ — adding, modifying, or debugging core functionalities.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Layer Structure

```
./
├── eval/__init__.py — Initializes the eval module
├── eval/harness.py — Adds parent to path when running directly
├── eval/scenarios_real.py — Contains real module snapshots
├── repoforge/__init__.py — Initializes the repoforge module
├── repoforge/adapters.py — Contains all valid target identifiers
├── repoforge/cli.py — Shared options factory for command line interface
└── repoforge/docs_generator.py — Generates documentation
```

## Critical Patterns

### Module Export Convention

Always export functions at the module level for easy access.

```python
# Example using real exported names
from eval.harness import make_fastapi_crud_module
```

### Shared Prompts Usage

Utilize shared prompts for consistent documentation generation.

```python
# Example
from repoforge.docs_prompts import index_prompt
```

## When to Use

- Implementing new evaluation scenarios
- Adapting modules for different target identifiers
- Generating documentation for core functionalities

## Adding a New Module

1. Create a new file in the `eval/` directory, e.g., `eval/new_module.py`
2. Define the necessary functions and export them
3. Update `__init__.py` to include the new module
4. Verify by running tests in the `eval/` directory

## Commands

```bash
python -m repoforge.cli
```

## Anti-Patterns

- **Don't**: Change function signatures in `eval/harness.py` — it breaks existing integrations.
- **Don't**: Remove exports from `repoforge/adapters.py` — it disrupts the expected behavior of dependent modules.

## Quick Reference

| Task                | File                        | Pattern                          |
|---------------------|-----------------------------|----------------------------------|
| Generate docs       | `repoforge/docs_generator.py` | `generate_docs`                  |
| Adapt for target    | `repoforge/adapters.py`     | `adapt_for_cursor`               |