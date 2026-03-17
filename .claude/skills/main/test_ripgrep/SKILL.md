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

Define an endpoint to create a new user using FastAPI.

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

- When adding new user management features in the test_ripgrep module.
- When needing to expose user data through an API.
- To debug user retrieval issues in the application.

## Commands

```bash
pytest tests/test_ripgrep.py
```

## Anti-Patterns

### Don't: Hardcode User Data

Hardcoding user data can lead to maintenance issues and security risks.

```python
# BAD
users = [{"name": "John Doe", "email": "john@example.com"}]
```

## Quick Reference

| Task               | Pattern                     |
|--------------------|-----------------------------|
| Create user        | `add_user(user_data)`       |
| List users         | `list_users()`              |