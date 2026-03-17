---
name: add-test-scorer-endpoint
description: >
  This skill covers patterns for creating and managing test scorers.
  Trigger: Load this skill when working with the test_scorer module.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: medium
  token_estimate: 450
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# add-test-scorer-endpoint

This skill covers patterns for creating and managing test scorers.

**Trigger**: Load this skill when working with the test_scorer module.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Get users | `get_users()` |
| Create user | `create_user()` |

## Critical Patterns (Summary)
- **Get Users**: Retrieve a list of users from the database.
- **Create User**: Add a new user to the database.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Get Users

Retrieve a list of users from the database using the `get_users` function.

```python
users = get_users()
```

### Create User

Add a new user to the database with the `create_user` function.

```python
new_user = create_user(name="John Doe", email="john@example.com")
```

## When to Use

- When you need to fetch user data for scoring.
- When creating new users for testing purposes.

## Commands

```bash
pytest tests/test_scorer.py
```

## Anti-Patterns

### Don't: Use hardcoded user data

Hardcoding user data can lead to maintenance issues and reduced test reliability.

```python
# BAD
user = create_user(name="Hardcoded User", email="hardcoded@example.com")
```
<!-- L3:END -->