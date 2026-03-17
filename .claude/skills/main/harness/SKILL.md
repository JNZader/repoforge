---
name: add-harness-endpoint
description: >
  This skill covers adding endpoints to the harness module.
  Trigger: When integrating new functionalities into the harness.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Create FastAPI CRUD Module

Use this pattern to create a CRUD module for FastAPI within the harness.

```python
from eval.harness import make_fastapi_crud_module

app = make_fastapi_crud_module("Item")
```

### Create Next.js Page Module

This pattern helps in generating a Next.js page module for the harness.

```python
from eval.harness import make_nextjs_page_module

page = make_nextjs_page_module("HomePage")
```

## When to Use

- When you need to expose new API endpoints in the harness.
- To create a new frontend page that interacts with the harness.
- When evaluating the performance of new features in the harness.

## Commands

```bash
python -m eval.harness
```

## Anti-Patterns

### Don't: Skip Path Management

Neglecting to manage the parent path can lead to module import errors.

```python
# BAD
import some_module  # Fails if not in the correct path
```

## Quick Reference

| Task                     | Pattern                          |
|--------------------------|----------------------------------|
| Create FastAPI module    | `make_fastapi_crud_module`      |
| Create Next.js page      | `make_nextjs_page_module`       |