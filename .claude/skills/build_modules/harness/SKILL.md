---
name: add-harness-modules
description: >
  Provides patterns to generate evaluation harness modules and score their outputs.
  Trigger: when working with the `harness` module in the eval layer.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 340
dependencies: []
related_skills: ["run-scenarios", "evaluate-code"]
load_priority: high
---

<!-- L1:START -->
# add-harness-modules

Creates FastAPI CRUD scaffolds and scoring utilities for the evaluation harness.

**Trigger**: when you need to extend or invoke `eval/harness.py` functionality.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| scaffold FastAPI CRUD | `make_fastapi_crud_module()` |
| score trigger precision | `score_trigger_precision(output, module)` |
| scaffold Next.js page | `make_nextjs_page_module()` |

## Critical Patterns (Summary)
- **Generate FastAPI CRUD Module**: use `make_fastapi_crud_module` to obtain route and schema dicts.
- **Score Trigger Precision**: apply `score_trigger_precision` to evaluate LLM output against a module spec.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Generate FastAPI CRUD Module

Creates a pair of dictionaries containing FastAPI route definitions and Pydantic schemas, ready to be injected into a running app.

```python
from eval.harness import make_fastapi_crud_module

routes, schemas = make_fastapi_crud_module()
# routes: {'/items': {'get': func, 'post': func}}
# schemas: {'Item': ItemModel}
```

### Score Trigger Precision

Evaluates how precisely the LLM output matches the expected module interface, returning a `ScoreResult` with a numeric score and explanation.

```python
from eval.harness import score_trigger