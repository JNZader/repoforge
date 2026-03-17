---
name: main-layer
description: >
  This layer owns the core functionality of the project, including evaluation and documentation generation.
  Trigger: When working in main/ — adding, modifying, or debugging core features and documentation.
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

### Module Export Convention

Always export functions at the module level for easy access.

```python
# Example using real exported names
from eval.harness import make_fastapi_crud_module
```

### Documentation Generation

Use the `generate_docs` function to create documentation from prompts.

```python
# Example
from repoforge.docs_generator import generate_docs
```

## When to Use

- Creating new evaluation modules
- Generating project documentation
- Modifying shared prompts for documentation

## Adding a New Module

1. Create a new file in the `eval/` directory, e.g., `eval/new_module.py`
2. Define the necessary functions and export them
3. Update the `__init__.py` file to include the new module
4. Verify by running the documentation generation command

## Commands

```bash
python -m repoforge.cli
```

## Anti-Patterns

- **Don't**: Change the structure of the `eval/` directory without updating imports — this will break module references.
- **Don't**: Modify shared prompts in `repoforge/docs_prompts.py` without coordinating with documentation updates — this can lead to inconsistencies in generated docs.

## Quick Reference

| Task                | File                          | Pattern                          |
|---------------------|-------------------------------|----------------------------------|
| Generate documentation | `repoforge/docs_generator.py` | `generate_docs`                  |
| Create a new module | `eval/new_module.py`         | `make_fastapi_crud_module`       |