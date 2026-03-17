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
├── repoforge/adapters.py — Contains valid target identifiers
├── repoforge/cli.py — Shared options factory
└── repoforge/docs_generator.py — Generates documentation
```

## Critical Patterns

### Module Initialization

Always initialize modules in `__init__.py` to ensure proper imports.

```python
# eval/__init__.py
from .harness import make_fastapi_crud_module
```

### Shared Options

Utilize the shared options factory in `cli.py` for consistent command-line interfaces.

```python
# repoforge/cli.py
def main():
    ...
```

## When to Use

- Implementing new evaluation scenarios
- Adapting modules for different targets
- Generating documentation for the project

## Adding a New Module

1. Create a new file in the `eval/` directory, e.g., `eval/new_module.py`.
2. Define the necessary functions and classes.
3. Update `eval/__init__.py` to include the new module.
4. Verify functionality by running tests in the `eval/` directory.

## Commands

```bash
python -m repoforge.cli
```

## Anti-Patterns

- **Don't**: Change the structure of `eval/harness.py` — it may break module imports across the project.
- **Don't**: Modify the shared options in `repoforge/cli.py` without updating all dependent modules — this can lead to inconsistent command-line behavior.

## Quick Reference

| Task                | File                        | Pattern                      |
|---------------------|-----------------------------|------------------------------|
| Initialize module   | `eval/__init__.py`         | `from .harness import ...`   |
| Generate docs       | `repoforge/docs_generator.py` | `generate_docs()`           |