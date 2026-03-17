---
name: add-test-scorer-endpoint
description: >
  This skill covers patterns for implementing scoring endpoints in tests.
  Trigger: When creating test cases for scoring functionality.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Create User for Scoring

Use `create_user` to set up a user for scoring tests.

```python
from tests.test_scorer import create_user

user = create_user(name="Test User", score=100)
```

### Retrieve Users for Scoring

Utilize `get_users` to fetch users for scoring validation.

```python
from tests.test_scorer import get_users

users = get_users()
```

## When to Use

- When setting up test cases for user scoring.
- To validate scoring logic against multiple users.
- During debugging of scoring-related test failures.

## Commands

```bash
pytest tests/test_scorer.py
```

## Anti-Patterns

### Don't: Use Hardcoded User Data

Hardcoding user data can lead to brittle tests that fail on changes.

```python
# BAD
user = create_user(name="Hardcoded User", score=50)
```

## Quick Reference

| Task                     | Pattern                          |
|--------------------------|----------------------------------|
| Create a test user      | `create_user(name="User", score=0)` |
| Fetch all test users    | `get_users()`                   |