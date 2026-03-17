---
name: test-compressor-fixtures
description: >
  This skill covers patterns for creating fixtures to test compression passes.
  Trigger: Load when working with test_compressor module.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: low
  token_estimate: 350
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# test-compressor-fixtures

This skill covers patterns for creating fixtures to test compression passes.

**Trigger**: Load when working with test_compressor module.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Create user fixture | `create_user_fixture` |
| Get user fixture | `get_user_fixture` |

## Critical Patterns (Summary)
- **Create User Fixture**: Use `create_user` to set up a user for testing.
- **Get User Fixture**: Utilize `get_user` to retrieve user data for tests.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Create User Fixture

This pattern demonstrates how to create a user fixture using the `create_user` function.

```python
from tests.test_compressor import create_user

def create_user_fixture():
    user = create_user(name="Test User", email="test@example.com")
    return user
```

### Get User Fixture

This pattern shows how to retrieve a user fixture using the `get_user` function.

```python
from tests.test_compressor import get_user

def get_user_fixture(user_id):
    user = get_user(user_id)
    return user
```

## When to Use

- When setting up tests that require user data.
- When validating compression passes with specific user scenarios.

## Commands

```bash
pytest tests/test_compressor.py
```

## Anti-Patterns

### Don't: Hardcode User Data

Hardcoding user data can lead to brittle tests that fail when data changes.

```python
# BAD
def create_hardcoded_user():
    return create_user(name="Hardcoded User", email="hardcoded@example.com")
```
<!-- L3:END -->