---
name: add-auth-endpoint
description: >
  This skill covers the implementation of authentication routes for user login and token validation.
  Trigger: When working with auth-related functionalities in the backend.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: medium
  token_estimate: 350
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# add-auth-endpoint

This skill covers the implementation of authentication routes for user login and token validation.

**Trigger**: When working with auth-related functionalities in the backend.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task               | Pattern                     |
|--------------------|-----------------------------|
| User login         | `login`                     |
| OAuth callback     | `callback`                  |
| Validate JWT token | `validate_token`            |
| User logout        | `logout`                    |

## Critical Patterns (Summary)
- **User Login**: Handles user authentication via GitHub OAuth.
- **Token Validation**: Validates JWT tokens for secure access.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### User Login

Handles user authentication via GitHub OAuth, allowing users to log in securely.

```python
from fastapi import APIRouter
from apps.server.app.routes.auth import login

router = APIRouter()

@router.post("/login")
async def user_login():
    return await login()
```

### Token Validation

Validates JWT tokens to ensure that requests are authenticated and authorized.

```python
from fastapi import Depends
from apps.server.app.routes.auth import validate_token

@router.get("/validate")
async def validate_user_token(token: str = Depends(validate_token)):
    return {"valid": True}
```

## When to Use

- When implementing user authentication in a FastAPI application.
- When validating JWT tokens for protected routes.

## Commands

```bash
docker-compose up
python apps/server/app/main.py
```

## Anti-Patterns

### Don't: Hardcode Secrets

Hardcoding secrets like client IDs or tokens is insecure and should be avoided.

```python
# BAD
client_id = "your_client_id_here"
```
<!-- L3:END -->