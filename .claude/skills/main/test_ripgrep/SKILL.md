---
name: add-test-ripgrep-endpoint
description: >
  This skill covers patterns for managing user endpoints in the test_ripgrep module.
  Trigger: When implementing user management features.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Create User Endpoint

Define a FastAPI endpoint to create a new user.

```python
from fastapi import FastAPI
from . import create_user

app = FastAPI()

@app.post("/users/")
def add_user(user_data: dict):
    return create_user(user_data)
```

### Get Users Endpoint

Set up an endpoint to retrieve a list of users.

```python
from fastapi import FastAPI
from . import get_users

app = FastAPI()

@app.get("/users/")
def list_users():
    return get_users()
```

## When to Use

- When adding new user management features to the test_ripgrep module.
- When integrating user data retrieval in the application.
- To debug user creation issues in the FastAPI application.

## Commands

```bash
pytest tests/test_ripgrep.py
```

## Anti-Patterns

### Don't: Use Blocking I/O

Using blocking I/O in FastAPI endpoints can lead to performance issues.

```python
# BAD
def blocking_user_creation():
    time.sleep(5)  # Simulates a blocking operation
```

## Quick Reference

| Task                     | Pattern                     |
|--------------------------|-----------------------------|
| Create user endpoint     | `add_user`                  |
| Get users endpoint       | `list_users`                |