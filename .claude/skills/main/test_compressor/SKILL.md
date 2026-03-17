---
name: test-compressor-fixtures
description: >
  This skill covers patterns for creating fixtures to test compression passes.
  Trigger: Load this skill when working with the test_compressor module.
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

**Trigger**: Load this skill when working with the test_compressor module.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Create a user fixture | `create_user` |
| Retrieve user data | `get_user` |

## Critical Patterns (Summary)
- **Create User Fixture**: Use `create_user` to set up user data for tests.
- **Retrieve User Data**: Utilize `get_user` to fetch user information during tests.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Create User Fixture

Use `create_user` to set up user data for tests, ensuring that the necessary user context is available.

```python
from tests.test_compressor import create_user

def test_user_creation():
    user = create_user(name="Test User", email="test@example.com")
    assert user.name == "Test User"
```

### Retrieve User Data

Utilize `get_user` to fetch user information during tests, allowing for validation of user-related functionality.

```python
from tests.test_compressor import get_user

def test_user_retrieval():
    user = get_user(user_id=1)
    assert user.email == "test@example.com"
```

## When to Use

- When setting up tests that require user data.
- When validating user-related functionality in compression tests.

## Commands

```bash
pytest tests/test_compressor.py
```

## Anti-Patterns

### Don't: Hardcode User Data

Hardcoding user data can lead to brittle tests that fail when data changes.

```python
# BAD
def test_hardcoded_user():
    assert get_user(user_id=1).name == "Hardcoded Name"
```
<!-- L3:END -->