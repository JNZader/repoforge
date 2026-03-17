---
name: add-harness-endpoint
description: >
  This skill covers patterns for adding endpoints in the harness layer.
  Trigger: When integrating new functionalities in the harness.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Create FastAPI CRUD Module

Use this pattern to generate a CRUD module for FastAPI.

```python
from eval.harness import make_fastapi_crud_module

app = make_fastapi_crud_module("Item", "items")
```

### Create Next.js Page Module

Utilize this pattern to create a new page module for Next.js.

```python
from eval.harness import make_nextjs_page_module

page = make_nextjs_page_module("HomePage", "/")
```

## When to Use

- When building RESTful APIs in the harness layer.
- When developing frontend pages that interact with backend services.
- To evaluate the performance of different module integrations.

## Commands

```bash
python -m eval.harness
```

## Anti-Patterns

### Don't: Skip Module Integration

Neglecting to integrate modules properly can lead to broken functionality.

```python
# BAD
from eval.harness import make_fastapi_crud_module

# Missing app initialization
```

## Quick Reference

| Task                     | Pattern                          |
|--------------------------|----------------------------------|
| Create FastAPI Module    | `make_fastapi_crud_module`      |
| Create Next.js Page      | `make_nextjs_page_module`       |