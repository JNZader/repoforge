---
name: main-layer
description: >
  This layer owns the core functionality of the project, including CLI commands, documentation generation, and module exports.
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

### Module Exporting

Always export necessary functions at the module level for easy access.

```python
# eval/harness.py
def make_fastapi_crud_module():
    pass
```

### Documentation Generation

Use the docs generator to create up-to-date documentation.

```python
# repoforge/docs_generator.py
def generate_docs():
    pass
```

## When to Use

- Creating new CLI commands
- Generating or updating project documentation
- Integrating new modules into the core functionality

## Adding a New CLI Command

1. Modify `repoforge/cli.py` to include the new command.
2. Implement the command logic in a new function.
3. Update the documentation in `repoforge/docs_generator.py`.
4. Verify the command works by running it in the terminal.

## Commands

```bash
python -m repoforge.cli
```

## Anti-Patterns

- **Don't**: Change the structure of `repoforge/cli.py` without updating all dependent modules — this can break command execution.
- **Don't**: Remove exports from `eval/harness.py` without ensuring all modules that rely on them are updated — this can lead to runtime errors.

## Quick Reference

| Task               | File                        | Pattern                     |
|--------------------|-----------------------------|-----------------------------|
| Add a new command   | `repoforge/cli.py`         | `def new_command():`       |
| Generate docs       | `repoforge/docs_generator.py` | `generate_docs()`          |
| Use shared prompts   | `repoforge/docs_prompts.py` | `index_prompt`             |