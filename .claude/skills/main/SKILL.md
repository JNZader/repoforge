---
name: main-layer
description: >
  This layer encompasses the core functionality of the project, including evaluation and adaptation modules.
  Trigger: When working in main/ — adding, modifying, or debugging core functionalities.
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

This skill covers the core functionalities of the project, including evaluation and adaptation modules.

**Trigger**: When working in main/ directory and its main responsibility.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Generate documentation | `generate_docs()` |

## Critical Patterns (Summary)
- **Module Initialization**: Ensure proper initialization of modules for evaluation.
- **Adaptation Handling**: Use the correct adaptation functions for target identifiers.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Module Initialization

Ensure proper initialization of modules for evaluation to avoid import errors.

```python
# Example using real exported names
from eval.harness import make_fastapi_crud_module
```

### Adaptation Handling

Use the correct adaptation functions for target identifiers to maintain compatibility.

```python
# Example
from repoforge.adapters import adapt_for_cursor
```

## When to Use

- When generating documentation for the project.
- When adapting modules for different target identifiers.

## Commands

```bash
python -m repoforge.cli
```

## Anti-Patterns

### Don't: Modify core modules without testing

Changing core modules can lead to unexpected behavior across the project.

```python
# BAD
from eval.harness import make_fastapi_crud_module  # Modifying this without tests can break functionality
```
<!-- L3:END -->