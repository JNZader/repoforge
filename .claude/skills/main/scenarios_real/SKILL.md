---
name: add-scenarios-real-endpoint
description: >
  This skill covers adding endpoints for scenarios_real.
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
reports_backend = get_reports_backend_module()
```

### Get Auth Backend Module

This function fetches the authentication backend module necessary for scenarios.

```python
auth_backend = get_auth_backend_module()
```

## When to Use

- When you need to integrate reporting features into the scenarios_real module.
- To implement authentication for user access in scenarios.
- When debugging issues related to backend module retrieval.

## Commands

```bash
python -m repoforge.cli skills
python -m repoforge.cli docs
```

## Anti-Patterns

### Don't: Hardcode Module Imports

Hardcoding module imports can lead to maintenance issues and reduce code flexibility.

```python
# BAD
from eval.scenarios_real import get_reports_backend_module
```

## Quick Reference

| Task | Pattern |
|------|---------|
| Retrieve reports backend | `get_reports_backend_module()` |
| Fetch auth backend | `get_auth_backend_module()` |