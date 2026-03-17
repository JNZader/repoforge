---
name: add-test-ripgrep-endpoint
description: >
  This skill covers patterns for managing user endpoints in the test_ripgrep module.
  Trigger: Load this skill when implementing user management features.
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
# add-test-ripgrep-endpoint

This skill covers patterns for managing user endpoints in the test_ripgrep module.

**Trigger**: Load this skill when implementing user management features.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task                     | Pattern                      |
|--------------------------|------------------------------|
| Create a user endpoint   | `create-user-endpoint`       |
| Get users endpoint       | `get-users-endpoint`         |

## Critical Patterns (Summary)
- **create-user-endpoint**: Defines a FastAPI endpoint for creating users.
- **get-users-endpoint**: Implements a FastAPI endpoint to retrieve users.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### create-user-endpoint

Defines a FastAPI endpoint for creating users using the `create_user` function.

```python
from fastapi import FastAPI
from your_module import create_user

app = FastAPI()

@app.post("/users/")
async def add_user(user: UserRouter):
    return create_user(user)
```

### get-users-endpoint

Implements a FastAPI endpoint to retrieve users using the `get_users` function.

```python
from fastapi import FastAPI
from your_module import get_users

app = FastAPI()

@app.get("/users/")
async def list_users():
    return get_users()
```

## When to Use

- When you need to create a new user in the application.
- When you want to retrieve a list of existing users.

## Commands

```bash
pytest tests/test_ripgrep.py
```

## Anti-Patterns

### Don't: Hardcode User Data

Hardcoding user data can lead to maintenance issues and security vulnerabilities.

```python
# BAD
user_data = {"name": "John Doe", "email": "john@example.com"}
```
<!-- L3:END -->