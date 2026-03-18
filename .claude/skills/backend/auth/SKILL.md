---
name: manage-auth-routes
description: >
  This skill covers the implementation of authentication routes for login, token validation, and logout.
  Trigger: When handling user authentication in the backend.
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
# manage-auth-routes

This skill covers the implementation of authentication routes for login, token validation, and logout.

**Trigger**: When handling user authentication in the backend.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task               | Pattern                  |
|--------------------|-------------------------|
| Implement login    | `login`                 |
| Handle callback    | `callback`              |
| Validate JWT token | `validate_token`        |
| Logout user        | `logout`                |

## Critical Patterns (Summary)
- **Implement login**: Use the `login` function to authenticate users via GitHub OAuth.
- **Handle callback**: Utilize the `callback` function to process the OAuth response.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Implement login

Use the `login` function to authenticate users via GitHub OAuth.

```python
from fastapi import APIRouter
from apps.server.app.routes.auth import login

router = APIRouter()

@router.get("/login")
async def github_login():
    return await login()
```

### Handle callback

Utilize the `callback` function to process the OAuth response.

```python
from fastapi import APIRouter
from apps.server.app.routes.auth import callback

router = APIRouter()

@router.get("/callback")
async def github_callback():
    return await callback()
```

## When to Use

- When implementing user authentication via GitHub OAuth.
- When validating JWT tokens for secure API access.

## Commands

```bash
docker-compose up
python apps/server/app/main.py
```

## Anti-Patterns

### Don't: Hardcode secrets

Hardcoding secrets can lead to security vulnerabilities.

```python
# BAD
SECRET_KEY = "mysecretkey"
```
<!-- L3:END -->