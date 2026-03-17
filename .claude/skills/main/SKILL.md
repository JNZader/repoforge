---
name: main-layer
description: >
  This layer encompasses the core functionality and utilities of the project.
  Trigger: When working in main/ — adding, modifying, or debugging core features.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: medium
  token_estimate: 800
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# main-layer

This skill covers the core functionality and utilities of the project.

**Trigger**: When working in main/ — adding, modifying, or debugging core features.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Generate documentation | `generate_docs()` |

## Critical Patterns (Summary)
- **Module Initialization**: Ensure proper initialization of modules in the main layer.
- **Command-Line Interface**: Utilize shared options for CLI commands.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Module Initialization

Ensure proper initialization of modules in the main layer to maintain a clean import structure.

```python
# eval/__init__.py
from .harness import make_fastapi_crud_module
```

### Command-Line Interface

Utilize shared options for CLI commands to maintain consistency across command executions.

```python
# repoforge/cli.py
def main():
    # Shared options setup
    pass
```

## When to Use

- When creating or modifying core functionalities.
- When integrating new features that require CLI support.

## Commands

```bash
python -m repoforge.cli
```

## Anti-Patterns

### Don't: Modify core modules without testing

Changing core modules can lead to unexpected behavior across the project.

```python
# BAD
def main():
    # Directly modifying core functionality without tests
    pass
```
<!-- L3:END -->