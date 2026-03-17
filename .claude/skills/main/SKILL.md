---
name: main-layer
description: >
  This layer encompasses the core functionality and utilities of the project.
  Trigger: When working in main/ — adding, modifying, or debugging core features.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: low
  token_estimate: 450
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
| Create a FastAPI CRUD module | `make_fastapi_crud_module()` |
| Generate a Next.js page module | `make_nextjs_page_module()` |

## Critical Patterns (Summary)
- **FastAPI CRUD Module Creation**: Use `make_fastapi_crud_module()` to scaffold a new CRUD API.
- **Next.js Page Module Generation**: Utilize `make_nextjs_page_module()` for creating a new page in Next.js.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### FastAPI CRUD Module Creation

This pattern allows you to quickly scaffold a CRUD API using FastAPI.

```python
from eval.harness import make_fastapi_crud_module

# Example usage
make_fastapi_crud_module('Item', 'items')
```

### Next.js Page Module Generation

This pattern helps in generating a new page module for a Next.js application.

```python
from eval.harness import make_nextjs_page_module

# Example usage
make_nextjs_page_module('HomePage', '/')
```

## When to Use

- When you need to create a new API endpoint for your application.
- When developing a new page for the frontend using Next.js.

## Commands

```bash
python -m eval.harness
```

## Anti-Patterns

### Don't: Modify core utilities without testing

Changing core functionalities can lead to unexpected behavior across the project.

```python
# BAD
def broken_function():
    # This change can break existing functionality
    pass
```
<!-- L3:END -->