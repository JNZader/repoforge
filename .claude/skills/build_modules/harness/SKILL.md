---
name: add-harness-modules
description: >
  Provides patterns to generate module scaffolds and evaluate LLM outputs with harness utilities.
  Trigger: when working with the `harness` module in eval layer.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills: ["run-scenarios", "score-evaluation"]
load_priority: high
---

<!-- L1:START -->
# add-harness-modules

Creates FastAPI CRUD scaffolds and scores LLM output precision using the harness utilities.

**Trigger**: when you need to scaffold a service layer or evaluate LLM output with the `harness` module.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Create FastAPI CRUD module | `make_fastapi_crud_module()` |
| Score trigger precision | `score_trigger_precision(output, module)` |
| Run all evaluation scenarios | `run_all()` |

## Critical Patterns (Summary)
- **Create FastAPI CRUD scaffolds**: use `make_fastapi_crud_module` to obtain route and model dictionaries.
- **Score trigger precision**: apply `score_trigger_precision` to get a `ScoreResult` reflecting how well output matches expected triggers.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Create FastAPI CRUD scaffolds

Generate ready‑to‑use FastAPI route and Pydantic model mappings in a single call.

```python
from eval.harness import make_fastapi_crud_module

# Returns (routes_dict, models_dict)
crud_routes, crud_models = make_fastapi_crud_module()
print(crud_routes)   # e.g., {'/items': <function ...>}
print(crud_models)   # e.g., {'Item': <class ...>}
```

### Score trigger precision

Assess how precisely LLM output triggers the expected behavior for a given module.

```python
from eval.harness import score_trigger_precision, ScoreResult

output = "Created item with ID 42"
module = {"expected_trigger": "item_created"}

result: ScoreResult = score_trigger_precision(output, module)
print(f"Precision: {result.precision:.2f}")
```

## When to Use

- When you need a quick FastAPI CRUD skeleton for a new service layer.
- When evaluating LLM‑generated code or logs against expected triggers.
- When running batch evaluations across multiple scenarios with `run_all`.

## Commands

```bash
# Run a single scenario with verbose logging
python -m eval.harness --scenario my_scenario --verbose

# Build the Docker image for the harness utilities
docker build -t eval-harness .
```

## Anti-Patterns

### Don't: Re‑create scaffolds inside a loop

Repeatedly calling scaffold generators wastes resources and can cause inconsistent state.

```python
# BAD
for item in items:
    routes, models = make_fastapi_crud_module()  # unnecessary repeated call
    process(item, routes, models)
```

Instead, call the generator once outside the loop and reuse the results.
<!-- L3:END -->