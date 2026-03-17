---
name: add-test-scorer-endpoint
description: >
  This skill covers patterns for implementing scoring functionality in tests.
  Trigger: When creating endpoints for test scoring.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Use `scorer` for scoring logic

Utilize the `scorer` function to encapsulate scoring logic for tests.

```python
from tests.test_scorer import scorer

def test_score():
    result = scorer(user_data)
    assert result == expected_score
```

### Create users with `create_user`

Leverage `create_user` to set up test users before scoring.

```python
from tests.test_scorer import create_user

def test_user_creation():
    user = create_user(name="Test User")
    assert user.name == "Test User"
```

## When to Use

- When setting up test scenarios that require user scoring.
- When validating user creation and scoring integration.
- To ensure completeness of test cases using `TestCompleteness`.

## Commands

```bash
pytest tests/test_scorer.py
```

## Anti-Patterns

### Don't: Use hardcoded user data

Hardcoding user data can lead to brittle tests that are hard to maintain.

```python
# BAD
def test_hardcoded_user():
    user = {"name": "Hardcoded User"}
    result = scorer(user)
```

## Quick Reference

| Task                     | Pattern                     |
|--------------------------|-----------------------------|
| Score a user             | `scorer(user_data)`         |
| Create a test user       | `create_user(name="...")`   |