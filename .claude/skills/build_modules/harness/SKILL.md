---
name: extend-harness-models
description: >
  Add parent to path when running directly.
  Trigger: when loading eval harness modules for CRUD, NextJS, or Go services.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: low
  token_estimate: 350
  dependencies: []
  related_skills: [eval-scenarios, repoforge-cli]
  load_priority: high
---

<!-- L1:START -->
# extend-harness-models

Add parent directory to sys.path when running eval harness modules directly.

**Trigger**: Running `eval/harness.py` or any harness module as a script.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Load harness module | `python -m eval.harness` |
| Run all scenarios | `python repoforge/cli.py eval` |
| Score trigger precision | `score_trigger_precision(output, module)` |
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Pattern 1: Add Parent to Path for Direct Execution

When running `eval/harness.py` directly, the `eval/` parent directory must be added to `sys.path` to resolve sibling imports. The module uses `pathlib.Path(__file__).parent.parent` to dynamically resolve the project root and insert it into the path.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
```

### Pattern 2: Score Trigger Precision Using Exported Functions

Use `score_trigger_precision` to evaluate how well an LLM output matches the expected trigger pattern for a given module. The function takes the raw output string and the generated module dict, returning a `ScoreResult` with precision metrics.

```python
from eval.harness import score_trigger_precision
result = score_trigger_precision(output, module_dict)
```

## When to Use

- Running eval harness scripts directly from the `eval/` directory
- Debugging module generation precision for FastAPI, NextJS, or Go services
- Validating that trigger patterns match expected module structures

## Commands

```bash
python -m eval.harness --scenario model --verbose
python repoforge/cli.py eval --all
```

## Anti-Patterns

### Don't: Run harness without path setup

Running `eval/harness.py` directly without adding the parent directory to `sys.path` causes `ImportError` for sibling modules. The script relies on `pathlib.Path(__file__).parent.parent` to locate project roots, and missing this setup breaks all module generation imports.

```python
# BAD: Missing path setup
# sys.path.insert(0, str(Path(__file__).parent.parent))
# from eval.harness import make_fastapi_crud_module
```
<!-- L3:END -->