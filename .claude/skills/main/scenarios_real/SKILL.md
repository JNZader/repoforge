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

Use this function to retrieve the backend module for reports.

```python
from eval.scenarios_real import get_reports_backend_module

reports_backend = get_reports_backend_module()
```

### Get Auth Backend Module

This function provides access to the authentication backend module.

```python
from eval.scenarios_real import get_auth_backend_module

auth_backend = get_auth_backend_module()
```

## When to Use

- When you need to implement reporting features in the scenarios_real module.
- When adding authentication capabilities to your application.
- To debug issues related to backend module integrations.

## Commands

```bash
python -m repoforge.cli
```

## Anti-Patterns

### Don't: Use Hardcoded Paths

Hardcoding paths can lead to maintenance issues and reduce code portability.

```python
# BAD
sys.path.append('/absolute/path/to/module')
```

## Quick Reference

| Task | Pattern |
|------|---------|
| Retrieve reports backend | `get_reports_backend_module()` |
| Access auth backend | `get_auth_backend_module()` |