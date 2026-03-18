---
name: add-auth-endpoint
description: >
  This skill covers the implementation of authentication routes.
  Trigger: When setting up auth functionality in the backend.
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
# add-auth-endpoint

This skill covers the implementation of authentication routes.

**Trigger**: When setting up auth functionality in the backend.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task               | Pattern                     |
|--------------------|-----------------------------|
| User login         | `login`                     |
| GitHub callback     | `callback`                  |
| Validate JWT token | `validate_token`            |
| User logout        | `logout`                    |

## Critical Patterns (Summary)
- **User login**: Handles user authentication via GitHub OAuth.
- **JWT validation**: Validates the JWT token for secure access.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### User login

Handles user authentication via GitHub OAuth.

```python
from fastapi import APIRouter
from apps.server.app.routes.auth import login

router = APIRouter()

@router.post("/login")
async def user_login():
    return await login()
```

### JWT validation

Validates the JWT token for secure access.

```python
from fastapi import Depends
from apps.server.app.routes.auth import validate_token

async def get_current_user(token: str = Depends(validate_token)):
    return token
```

## When to Use

- When implementing user authentication in a FastAPI application.
- When needing to validate JWT tokens for protected routes.

## Commands

```bash
pip install fastapi
pip install sqlalchemy
```

## Anti-Patterns

### Don't: Hardcode secrets

Hardcoding secrets can lead to security vulnerabilities.

```python
# BAD
SECRET_KEY = "mysecretkey"
```
<!-- L3:END -->