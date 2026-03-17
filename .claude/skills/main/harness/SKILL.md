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

### Generate Next.js Page Module

This pattern helps in generating a Next.js page module for the harness.

```python
from eval.harness import make_nextjs_page_module

page = make_nextjs_page_module("HomePage")
```

## When to Use

- When building RESTful APIs using FastAPI in the harness.
- When creating frontend pages with Next.js for the harness.
- To evaluate the performance of different modules in the harness.

## Commands

```bash
python repoforge/cli.py run
python repoforge/cli.py test
```

## Anti-Patterns

### Don't: Hardcode Paths

Hardcoding paths can lead to issues with module imports and execution.

```python
# BAD
import sys
sys.path.append('/absolute/path/to/harness')
```

## Quick Reference

| Task                     | Pattern                          |
|--------------------------|----------------------------------|
| Create FastAPI Module    | `make_fastapi_crud_module`      |
| Generate Next.js Page    | `make_nextjs_page_module`       |