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

### Scenario Management

Use scenarios to manage real module snapshots effectively.

```python
# Example
from eval.scenarios_real import get_reports_backend_module
```

## When to Use

- Implementing core evaluation logic
- Adapting modules for different targets
- Generating documentation for the project

## Adding a New Module

1. Create a new file in the `eval/` directory, e.g., `eval/new_module.py`
2. Define the necessary functions and classes
3. Export the new module in `eval/__init__.py`
4. Verify functionality by running tests in the `eval/` directory

## Commands

```bash
python -m repoforge.cli
```

## Anti-Patterns

- **Don't**: Change the structure of `eval/harness.py` — it breaks the import paths for dependent modules.
- **Don't**: Modify the exports in `repoforge/adapters.py` without updating all dependent modules — it leads to runtime errors.

## Quick Reference

| Task               | File                        | Pattern                          |
|--------------------|-----------------------------|----------------------------------|
| Generate docs      | `repoforge/docs_generator.py` | `generate_docs`                  |
| Adapt for targets  | `repoforge/adapters.py`     | `adapt_for_cursor`               |
| Run CLI            | `repoforge/cli.py`          | `main`                           |