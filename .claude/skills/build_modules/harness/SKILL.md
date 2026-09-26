---
name: add-harness-modules
description: > 
  Provides patterns for generating evaluation harness modules.
  Trigger: harness
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills: [generate-eval-report, adapt-eval-modules]
load_priority: high
---

<!-- L1:START -->
# add-harness-modules

Creates evaluation harness components from the exported factory functions.

**Trigger**: when a `harness` file is edited or executed directly.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Build FastAPI CRUD | `make_fastapi_crud_module(name, schema)` |
| Build Next.js page | `make_nextjs_page_module(route, component)` |
| Score precision | `score_trigger_precision(result)` |

## Critical Patterns (Summary)
- **Create FastAPI CRUD module**: use `make_fastapi_crud_module` with explicit schema.
- **Score trigger precision**: feed a `ScoreResult` into `score_trigger_precision`.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Create FastAPI CRUD module

Generate a ready‑to‑run FastAPI CRUD layer by supplying a module name and a Pydantic schema. The function returns a string containing the module source, which can be written to disk or executed via `exec`.

```python
from eval.harness import make_fastapi_crud_module

schema = """
class Item(BaseModel):
    id: int
    name: str
"""
module_code = make_fastapi_crud_module(name="item", schema=schema)
print(module_code)  # write to a .py file or exec()
```

### Score trigger precision

After running a harness, wrap the raw JSON output in `ScoreResult` and pass it to `score_trigger_precision` to obtain a numeric precision metric.

```python
from eval.harness import ScoreResult, score_trigger_precision

raw = {"trigger": "model", "matched": True}
result = ScoreResult(**raw)
precision = score_trigger_precision(result)
print(f"Precision: {precision:.2f}")
```

## When to Use

- When you need a quick CRUD API for a new data model during evaluation.
- When generating a Next.js page to display evaluation results.
- When validating how accurately a harness detects the intended trigger.

## Commands

```bash
# Run the harness with explicit flags
python eval/harness.py --model my_model --scenario test_case --verbose

# Build and test inside Docker
docker run --rm -v "$(pwd)":/app python:3.11 bash -c "pip install -r requirements.txt && python eval/harness.py --model my_model"
```

## Anti-Patterns

### Don't: Call factory without required arguments

Omitting required parameters leads to runtime `TypeError` and broken modules.

```python
# BAD: missing the required `schema` argument
module_code = make_fastapi_crud_module(name="item")
```
<!-- L3:END -->