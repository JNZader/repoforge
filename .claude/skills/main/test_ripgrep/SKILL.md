---
name: add-test-ripgrep-endpoint
description: >
  This skill covers patterns for adding endpoints to the user management router.
  Trigger: When implementing new user-related features in test_ripgrep.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Create User Endpoint

Define a FastAPI endpoint to create a new user.

```python
from fastapi import APIRouter
from pydantic import BaseModel
from . import create_user

router = APIRouter()

class UserCreate(BaseModel):
    username: str
    email: str

@router.post("/users/")
async def create_user_endpoint(user: UserCreate):
    return await create_user(user)
```

### Get Users Endpoint

Implement an endpoint to retrieve a list of users.

```python
from fastapi import APIRouter
from . import get_users

router = APIRouter()

@router.get("/users/")
async def get_users_endpoint():
    return await get_users()
```

## When to Use

- When adding new user management features in the test_ripgrep module.
- When integrating user data retrieval in the application.
- To debug user creation issues in the user management router.

## Commands

```bash
pytest tests/test_ripgrep.py
```

## Anti-Patterns

### Don't: Use Blocking Calls

Using blocking calls in FastAPI endpoints can lead to performance issues.

```python
# BAD
def create_user_endpoint(user: UserCreate):
    return create_user(user)  # This blocks the event loop
```

## Quick Reference

| Task                     | Pattern                          |
|--------------------------|----------------------------------|
| Create user endpoint     | `create_user_endpoint`           |
| Get users endpoint       | `get_users_endpoint`             |