---
name: main-layer
description: >
  This layer owns the core functionality of the project, including CLI commands, documentation generation, and evaluation scenarios.
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
├── repoforge/cli.py — Shared options factory for CLI commands
├── repoforge/docs_generator.py — Generates project documentation
├── repoforge/docs_prompts.py — Shared system prompts for documentation
└── repoforge/docsify.py — Main entry point for documentation building
```

## Critical Patterns

### CLI Command Structure

All CLI commands should follow the structure defined in `repoforge/cli.py`.

```python
# Example using real exported names
from repoforge.cli import main
```

### Documentation Generation

Use `repoforge/docs_generator.py` to create documentation for new features.

```python
# Example
from repoforge.docs_generator import generate_docs
```

## When to Use

- Creating new CLI commands
- Generating documentation for new modules
- Implementing evaluation scenarios

## Adding a New CLI Command

1. Modify `repoforge/cli.py` to include the new command.
2. Implement the command logic in a new function.
3. Update the documentation in `repoforge/docs_generator.py`.
4. Test the command using the CLI.

## Commands

```bash
python -m repoforge.cli
```

## Anti-Patterns

- **Don't**: Change the structure of `repoforge/cli.py` without updating all dependent modules — this can break existing CLI commands.
- **Don't**: Modify `eval/scenarios_real.py` without ensuring compatibility with the main evaluation logic — this can lead to inconsistent behavior.

## Quick Reference

| Task                | File                          | Pattern                          |
|---------------------|-------------------------------|----------------------------------|
| Add a new CLI command | `repoforge/cli.py`          | `from repoforge.cli import main` |
| Generate documentation | `repoforge/docs_generator.py` | `from repoforge.docs_generator import generate_docs` |