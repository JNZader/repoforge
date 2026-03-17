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
└── repoforge/disclosure.py — Manages tier markers
```

## Critical Patterns

### Module Initialization

Always initialize modules in `__init__.py` to ensure proper imports.

```python
# eval/__init__.py
from .harness import make_fastapi_crud_module
```

### Command Line Interface

Use `repoforge/cli.py` for shared command line options.

```python
# repoforge/cli.py
import click

@click.command()
def main():
    pass
```

## When to Use

- Implementing new evaluation scenarios
- Adapting modules for different targets
- Generating documentation for core functionalities

## Adding a New Module

1. Create a new file in the `eval/` directory, e.g., `eval/new_module.py`.
2. Define the necessary functions and classes.
3. Update `eval/__init__.py` to include the new module.
4. Verify by running the CLI commands to ensure integration.

## Commands

```bash
python -m repoforge.cli
```

## Anti-Patterns

- **Don't**: Modify `eval/harness.py` without updating dependent modules — this can break the entire evaluation flow.
- **Don't**: Change the structure of `repoforge/adapters.py` without notifying other layers — it can lead to integration issues across the project.

## Quick Reference

| Task                | File                        | Pattern                       |
|---------------------|-----------------------------|-------------------------------|
| Initialize module   | `eval/__init__.py`         | `from .harness import ...`    |
| Add CLI command     | `repoforge/cli.py`         | `@click.command()`            |
| Generate docs       | `repoforge/docs_generator.py` | `generate_docs()`            |