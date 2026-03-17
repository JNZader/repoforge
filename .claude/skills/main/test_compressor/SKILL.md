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
- **Create User**: Use `create_user` to set up test users.
- **Get Users**: Retrieve users with `get_users` for validation.
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

Retrieve users with `get_users` to validate the created users in tests.

```python
from tests.test_compressor import get_users

users = get_users()
assert len(users) > 0
```

## When to Use

- When initializing test data for compression tests.
- To ensure user data is available for validation during tests.

## Commands

```bash
pytest tests/test_compressor.py
```

## Anti-Patterns

### Don't: Create Users Without Validation

Creating users without checking existing data can lead to duplicates and test failures.

```python
# BAD
from tests.test_compressor import create_user

create_user(name="Duplicate User", email="duplicate@example.com")
create_user(name="Duplicate User", email="duplicate@example.com")  # This can cause issues
```
<!-- L3:END -->