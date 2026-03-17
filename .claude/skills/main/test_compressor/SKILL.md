---
name: create-test-compressor-user
description: >
  This skill covers creating users for testing compression passes.
  Trigger: Load this skill when setting up test scenarios for the test_compressor module.
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
# create-test-compressor-user

This skill covers creating users for testing compression passes.

**Trigger**: Load this skill when setting up test scenarios for the test_compressor module.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Create a user for tests | `create_user` |

## Critical Patterns (Summary)
- **Create User**: Use `create_user` to set up test users.
- **Get Users**: Retrieve users with `get_users` for validation in tests.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Create User

Use `create_user` to set up test users for the compression tests.

```python
from tests.test_compressor import create_user

user = create_user(name="Test User", email="test@example.com")
```

### Get Users

Retrieve users with `get_users` to validate the test scenarios.

```python
from tests.test_compressor import get_users

users = get_users()
```

## When to Use

- When you need to create users for testing the compression functionality.
- When validating user data in compression tests.

## Commands

```bash
pytest tests/test_compressor.py
```

## Anti-Patterns

### Don't: Create Users Without Validation

Creating users without validating their data can lead to unreliable tests.

```python
# BAD
from tests.test_compressor import create_user

create_user(name="", email="invalid-email")
```
<!-- L3:END -->