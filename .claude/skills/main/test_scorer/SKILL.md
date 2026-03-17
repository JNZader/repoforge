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

Utilize the `scorer` function to implement the core scoring logic in your tests.

```python
from tests.test_scorer import scorer

result = scorer(user_data)
```

### Create users with `create_user`

Leverage the `create_user` function to set up test users for scoring.

```python
from tests.test_scorer import create_user

user = create_user(name="Test User", score=100)
```

## When to Use

- When you need to score test results based on user data.
- To set up users for various test scenarios.
- When validating the completeness of test cases.

## Commands

```bash
pytest tests/test_scorer.py
```

## Anti-Patterns

### Don't: Use hardcoded user data

Hardcoding user data can lead to brittle tests that are difficult to maintain.

```python
# BAD
user = {"name": "Hardcoded User", "score": 50}
```

## Quick Reference

| Task                     | Pattern                     |
|--------------------------|-----------------------------|
| Score a user             | `scorer(user_data)`         |
| Create a test user       | `create_user(name, score)`  |