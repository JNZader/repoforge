---
name: add-auth-endpoint
description: >
  This skill covers the implementation of authentication routes.
  Trigger: When setting up auth-related endpoints in the backend.
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
# add-auth-endpoint

This skill covers the implementation of authentication routes.

**Trigger**: When setting up auth-related endpoints in the backend.
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
- **User Login**: Handles user authentication via GitHub OAuth.
- **Token Validation**: Validates JWT tokens for secure access.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### User Login

Handles user authentication via GitHub OAuth, redirecting users to the GitHub login page.

```python
from fastapi import APIRouter
from apps.server.app.routes.auth import login

router = APIRouter()

@router.get("/login")
async def github_login():
    return await login()
```

### Token Validation

Validates JWT tokens to ensure secure access to protected routes.

```python
from fastapi import Depends
from apps.server.app.routes.auth import validate_token

@router.get("/protected")
async def protected_route(token: str = Depends(validate_token)):
    return {"message": "Access granted"}
```

## When to Use

- When implementing user authentication for a web application.
- When securing API endpoints with JWT tokens.

## Commands

```bash
docker-compose up
python apps/server/app/main.py
```

## Anti-Patterns

### Don't: Hardcode Secrets

Hardcoding secrets in your code can lead to security vulnerabilities.

```python
# BAD
SECRET_KEY = "mysecretkey"
```
<!-- L3:END -->