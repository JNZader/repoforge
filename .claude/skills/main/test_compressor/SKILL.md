---
name: create-test-compressor-user
description: >
  This skill covers creating users for testing compression passes.
  Trigger: Load this skill when setting up test_compressor fixtures.
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

**Trigger**: Load this skill when setting up test_compressor fixtures.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Create a user for tests | `create_user` |

## Critical Patterns (Summary)
- **Create User**: Use `create_user` to set up a user for testing.
- **Get Users**: Retrieve users with `get_users` for validation in tests.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Create User

Use `create_user` to set up a user for testing compression passes.

```python
from tests.test_compressor import create_user

user = create_user(username="test_user", password="secure_password")
```

### Get Users

Retrieve users with `get_users` for validation in tests.

```python
from tests.test_compressor import get_users

users = get_users()
assert len(users) > 0
```

## When to Use

- When initializing test data for compression tests.
- When validating user-related functionality in compression scenarios.

## Commands

```bash
pytest tests/test_compressor.py
```

## Anti-Patterns

### Don't: Hardcode User Data

Hardcoding user data can lead to brittle tests that fail on changes.

```python
# BAD
user = create_user(username="hardcoded_user", password="12345")
```
<!-- L3:END -->