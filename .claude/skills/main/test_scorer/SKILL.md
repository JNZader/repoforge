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
| Get users | `get_users()` |
| Create user | `create_user()` |

## Critical Patterns (Summary)
- **Get Users**: Retrieve a list of users for scoring.
- **Create User**: Add a new user to the scoring system.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Get Users

Retrieve a list of users for scoring purposes.

```python
users = get_users()
```

### Create User

Add a new user to the scoring system.

```python
new_user = create_user(name="John Doe", score=0)
```

## When to Use

- When you need to retrieve users for scoring in tests.
- When adding new users to the scoring system for evaluation.

## Commands

```bash
pytest tests/test_scorer.py
```

## Anti-Patterns

### Don't: Use hardcoded user data

Hardcoding user data can lead to brittle tests that fail with changes in user requirements.

```python
# BAD
user = create_user(name="Hardcoded User", score=100)
```
<!-- L3:END -->