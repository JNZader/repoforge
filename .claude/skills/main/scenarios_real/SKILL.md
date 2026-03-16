---
name: add-scenarios-real-endpoint
description: >
  This skill covers adding endpoints for scenarios in the real module.
  Trigger: When integrating new functionality into the scenarios_real module.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Get Reports Backend Module

Use this function to retrieve the reports backend module for scenarios.

```python
from eval.scenarios_real import get_reports_backend_module

reports_backend = get_reports_backend_module()
```

### Get Auth Backend Module

Utilize this function to access the authentication backend module.

```python
from eval.scenarios_real import get_auth_backend_module

auth_backend = get_auth_backend_module()
```

## When to Use

- When you need to integrate reporting features into the scenarios_real module.
- When implementing authentication for user access in scenarios.
- To debug issues related to backend module retrieval in scenarios.

## Commands

```bash
python -m repoforge.cli
```

## Anti-Patterns

### Don't: Hardcode Module Paths

Hardcoding paths can lead to maintenance issues and reduce code portability.

```python
# BAD
from eval.scenarios_real import get_reports_backend_module as reports_backend
```

## Quick Reference

| Task | Pattern |
|------|---------|
| Retrieve reports backend | `get_reports_backend_module()` |
| Access auth backend | `get_auth_backend_module()` |