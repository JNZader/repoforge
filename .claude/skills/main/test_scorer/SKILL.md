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
| Create a user | `create_user` |
| Get users | `get_users` |

## Critical Patterns (Summary)
- **Create User**: Use `create_user` to add a new user to the scorer.
- **Get Users**: Utilize `get_users` to retrieve a list of users for scoring.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Create User

Use `create_user` to add a new user to the scorer, ensuring the user is properly initialized.

```python
from tests.test_scorer import create_user

new_user = create_user(name="John Doe", score=0)
```

### Get Users

Utilize `get_users` to retrieve a list of users for scoring, which can be used for various operations.

```python
from tests.test_scorer import get_users

users = get_users()
```

## When to Use

- When you need to add a new user to the scoring system.
- When retrieving all users for evaluation or reporting.

## Commands

```bash
pytest tests/test_scorer.py
```

## Anti-Patterns

### Don't: Use hardcoded values

Hardcoding values can lead to maintenance issues and reduce flexibility.

```python
# BAD
user = create_user(name="Hardcoded User", score=100)
```
<!-- L3:END -->