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

app = make_fastapi_crud_module("Item", "items")
```

### Create Next.js Page Module

This pattern helps in generating a Next.js page module for the harness.

```python
from eval.harness import make_nextjs_page_module

page = make_nextjs_page_module("HomePage", "/")
```

## When to Use

- When building RESTful APIs in the harness.
- When developing frontend pages that interact with the harness.
- To evaluate the performance of new modules added to the harness.

## Commands

```bash
python -m eval.harness
python -m repoforge.cli
```

## Anti-Patterns

### Don't: Skip Module Integration

Skipping module integration can lead to broken functionalities and untested code.

```python
# BAD
from eval.harness import make_fastapi_crud_module

# Missing integration step
```

## Quick Reference

| Task | Pattern |
|------|---------|
| Create FastAPI CRUD | `make_fastapi_crud_module` |
| Create Next.js Page | `make_nextjs_page_module` |