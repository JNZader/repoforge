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

| Task               | Pattern                  |
|--------------------|-------------------------|
| Login user         | `login`                 |
| Validate token     | `validate_token`        |

## Critical Patterns (Summary)
- **Login User**: Handles user login via GitHub OAuth.
- **Validate Token**: Validates JWT tokens for authenticated requests.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Login User

Handles user login via GitHub OAuth, redirecting to the callback after authentication.

```python
from fastapi import APIRouter
from apps.server.app.routes.auth import login

router = APIRouter()

@router.get("/login")
async def github_login():
    return await login()
```

### Validate Token

Validates JWT tokens to ensure the user is authenticated for protected routes.

```python
from fastapi import Depends
from apps.server.app.routes.auth import validate_token

async def get_current_user(token: str = Depends(validate_token)):
    return token
```

## When to Use

- When implementing user authentication in a FastAPI application.
- When securing routes that require user validation.

## Commands

```bash
docker-compose up
python apps/server/app/main.py
```

## Anti-Patterns

### Don't: Hardcode Secrets

Hardcoding secrets like JWT keys is insecure and should be avoided.

```python
# BAD
JWT_SECRET = "mysecretkey"
```
<!-- L3:END -->