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

Use this pattern to retrieve the reports backend module for scenarios.

```python
from eval.scenarios_real import get_reports_backend_module

reports_backend = get_reports_backend_module()
```

### Get Auth Backend Module

This pattern allows you to access the authentication backend module.

```python
from eval.scenarios_real import get_auth_backend_module

auth_backend = get_auth_backend_module()
```

## When to Use

- When you need to fetch the reports backend for data processing.
- To implement authentication features in your application.
- During debugging to ensure backend modules are correctly loaded.

## Commands

```bash
python -m repoforge.cli
```

## Anti-Patterns

### Don't: Hardcode Module Imports

Hardcoding imports can lead to maintenance issues and reduce code flexibility.

```python
# BAD
from eval.scenarios_real import get_reports_backend_module as reports
reports = get_reports_backend_module()
```

## Quick Reference

| Task | Pattern |
|------|---------|
| Fetch reports backend | `get_reports_backend_module()` |
| Access auth backend | `get_auth_backend_module()` |