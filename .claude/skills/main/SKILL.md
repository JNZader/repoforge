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
  token_estimate: 450
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
| Create a FastAPI CRUD module | `make_fastapi_crud_module()` |

## Critical Patterns (Summary)
- **FastAPI CRUD Module**: Use `make_fastapi_crud_module` to quickly scaffold a CRUD API.
- **Adaptation for Targets**: Utilize `adapt_for_*` functions to ensure compatibility with various target identifiers.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### FastAPI CRUD Module

Use `make_fastapi_crud_module` to quickly scaffold a CRUD API for your data models.

```python
from eval.harness import make_fastapi_crud_module

app = make_fastapi_crud_module(model_name="User")
```

### Adaptation for Targets

Utilize `adapt_for_*` functions to ensure compatibility with various target identifiers.

```python
from repoforge.adapters import adapt_for_cursor

result = adapt_for_cursor(data)
```

## When to Use

- When creating new API endpoints for data models.
- When adapting data for different target systems.

## Commands

```bash
python -m eval.harness
python -m repoforge.cli
```

## Anti-Patterns

### Don't: Modify core evaluation logic without testing

Changing core evaluation logic can lead to unexpected behavior across the project.

```python
# BAD
def faulty_logic():
    return "This will break things!"
```
<!-- L3:END -->