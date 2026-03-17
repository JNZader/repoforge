---
name: add-test-scorer-endpoint
description: >
  This skill covers patterns for implementing scoring functionality in tests.
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

This skill covers patterns for implementing scoring functionality in tests.

**Trigger**: Load this skill when working with the test_scorer module.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Create a user for scoring | `create_user` |
| Retrieve users for scoring | `get_users` |

## Critical Patterns (Summary)
- **Create User**: Use `create_user` to add a new user for scoring.
- **Get Users**: Use `get_users` to retrieve a list of users for scoring.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Create User for Scoring

Use `create_user` to add a new user for scoring purposes in your tests.

```python
from tests.test_scorer import create_user

new_user = create_user(name="Test User", score=100)
```

### Get Users for Scoring

Use `get_users` to retrieve a list of users that can be scored.

```python
from tests.test_scorer import get_users

users = get_users()
```

## When to Use

- When you need to set up users for scoring in your test cases.
- When you want to retrieve existing users to evaluate their scores.

## Commands

```bash
pytest tests/test_scorer.py
```

## Anti-Patterns

### Don't: Hardcode User Data

Hardcoding user data can lead to brittle tests that fail when data changes.

```python
# BAD
new_user = create_user(name="Hardcoded User", score=50)
```
<!-- L3:END -->