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

app = make_fastapi_crud_module("Item")
```

### Create Next.js Page Module

Utilize this pattern to create a new page module for Next.js.

```python
from eval.harness import make_nextjs_page_module

page = make_nextjs_page_module("HomePage")
```

## When to Use

- When you need to expose a new API endpoint in the harness.
- To create a new frontend page that interacts with the backend.
- When evaluating the performance of different module integrations.

## Commands

```bash
python -m eval.harness
```

## Anti-Patterns

### Don't: Hardcode Paths

Hardcoding paths can lead to maintenance issues and reduce flexibility.

```python
# BAD
sys.path.append('/absolute/path/to/module')
```

## Quick Reference

| Task                     | Pattern                          |
|--------------------------|----------------------------------|
| Create FastAPI Module    | `make_fastapi_crud_module`      |
| Create Next.js Page      | `make_nextjs_page_module`       |