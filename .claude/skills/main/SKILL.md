---
name: main-layer
description: >
  This layer owns the core functionality of the project, including evaluation and documentation generation.
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
├── repoforge/cli.py — Shared options factory
├── repoforge/docs_generator.py — Generates documentation
├── repoforge/docs_prompts.py — Shared system prompts
└── repoforge/docsify.py — Main entry point for documentation
```

## Critical Patterns

### Module Initialization

Always initialize modules in `__init__.py` to ensure proper imports.

```python
# eval/__init__.py
from .harness import make_fastapi_crud_module
```

### Documentation Generation

Use the `generate_docs` function to create documentation files.

```python
# repoforge/docs_generator.py
def generate_docs():
    # Implementation here
```

## When to Use

- Creating new evaluation scenarios
- Generating project documentation
- Modifying shared CLI options

## Adding a New Module

1. Create a new file in the `eval/` directory, e.g., `eval/new_module.py`.
2. Implement the required functionality.
3. Update `eval/__init__.py` to include the new module.
4. Verify by running the documentation generation command.

## Commands

```bash
python -m repoforge.cli
```

## Anti-Patterns

- **Don't**: Modify `eval/harness.py` without updating dependent modules — it can break the entire evaluation flow.
- **Don't**: Change the structure of `repoforge/docs_prompts.py` without ensuring all documentation calls are updated — it can lead to missing prompts in generated docs.

## Quick Reference

| Task                | File                          | Pattern                     |
|---------------------|-------------------------------|-----------------------------|
| Generate Docs       | `repoforge/docs_generator.py` | `generate_docs()`           |
| Add CLI Options     | `repoforge/cli.py`           | `main()`                    |
| Initialize Module   | `eval/__init__.py`           | `from .harness import ...`  |