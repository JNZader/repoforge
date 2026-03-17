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

This skill covers the core functionality and application logic of the project.

**Trigger**: When working in main/ directory and its main responsibility.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Create a FastAPI CRUD module | `make_fastapi_crud_module()` |
| Generate a Next.js page module | `make_nextjs_page_module()` |

## Critical Patterns (Summary)
- **FastAPI CRUD Module Creation**: Use `make_fastapi_crud_module()` to scaffold CRUD operations.
- **Next.js Page Module Generation**: Utilize `make_nextjs_page_module()` for creating Next.js pages.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### FastAPI CRUD Module Creation

This pattern allows for the quick setup of CRUD operations in a FastAPI application.

```python
from eval.harness import make_fastapi_crud_module

# Example usage
make_fastapi_crud_module(model_name="User", db_model="UserDB")
```

### Next.js Page Module Generation

This pattern facilitates the creation of a new page in a Next.js application.

```python
from eval.harness import make_nextjs_page_module

# Example usage
make_nextjs_page_module(page_name="HomePage")
```

## When to Use

- When you need to implement CRUD operations for a new model in FastAPI.
- When generating new pages for a Next.js frontend.

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