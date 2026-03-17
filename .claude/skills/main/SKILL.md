---
name: main-layer
description: >
  This layer encompasses the core functionality of the project, managing the main application logic and integrations.
  Trigger: When working in main/ — adding, modifying, or debugging core application features.
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

This layer encompasses the core functionality of the project, managing the main application logic and integrations.

**Trigger**: When working in main/ — adding, modifying, or debugging core application features.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Create a FastAPI CRUD module | `make_fastapi_crud_module()` |

## Critical Patterns (Summary)
- **FastAPI CRUD Module**: Use `make_fastapi_crud_module()` to quickly scaffold a CRUD API.
- **Next.js Page Module**: Utilize `make_nextjs_page_module()` for generating Next.js pages.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### FastAPI CRUD Module

Use `make_fastapi_crud_module()` to quickly scaffold a CRUD API for your data models.

```python
from eval.harness import make_fastapi_crud_module

app = make_fastapi_crud_module(model_name="Item")
```

### Next.js Page Module

Utilize `make_nextjs_page_module()` for generating Next.js pages based on your application structure.

```python
from eval.harness import make_nextjs_page_module

page = make_nextjs_page_module(page_name="HomePage")
```

## When to Use

- When you need to create RESTful APIs for your data models.
- When integrating frontend components with backend services.

## Commands

```bash
python -m eval.harness
```

## Anti-Patterns

### Don't: Modify core logic without testing

Changing core application logic without proper testing can lead to unexpected behavior across the application.

```python
# BAD
def some_core_function():
    # Directly modifying shared state
    global shared_state
    shared_state = "new_value"
```
<!-- L3:END -->