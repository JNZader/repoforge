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

Define an endpoint to create a new user using the UserRouter.

```python
from fastapi import FastAPI
from tests.test_ripgrep import create_user, UserRouter

app = FastAPI()
app.include_router(UserRouter)

@app.post("/users/")
def add_user(user_data: dict):
    return create_user(user_data)
```

### Get Users Endpoint

Set up an endpoint to retrieve a list of users.

```python
from fastapi import FastAPI
from tests.test_ripgrep import get_users, UserRouter

app = FastAPI()
app.include_router(UserRouter)

@app.get("/users/")
def list_users():
    return get_users()
```

## When to Use

- When adding new user management features to the test_ripgrep module.
- When integrating user data retrieval in the application.
- To debug user creation issues in the test_ripgrep context.

## Commands

```bash
pytest tests/test_ripgrep.py
```

## Anti-Patterns

### Don't: Use Global State

Using global variables for user data can lead to unpredictable behavior.

```python
# BAD
users = []

def add_user(user):
    users.append(user)
```

## Quick Reference

| Task               | Pattern                      |
|--------------------|------------------------------|
| Create a user      | `create_user(user_data)`     |
| List users         | `get_users()`                |