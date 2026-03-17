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
- To create a new frontend page that interacts with the harness.
- When evaluating the performance of different module integrations.

## Commands

```bash
python repoforge/cli.py run
python repoforge/cli.py test
```

## Anti-Patterns

### Don't: Hardcode Paths

Hardcoding paths can lead to maintenance issues and reduce flexibility.

```python
# BAD
sys.path.append('/absolute/path/to/harness')
```

## Quick Reference

| Task                     | Pattern                          |
|--------------------------|----------------------------------|
| Add FastAPI endpoint     | `make_fastapi_crud_module`      |
| Create Next.js page      | `make_nextjs_page_module`       |