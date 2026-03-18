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
| Handle callback     | `callback`              |
| Validate JWT token | `validate_token`        |
| Logout user        | `logout`                |

## Critical Patterns (Summary)
- **Login User**: Implements user login via GitHub OAuth.
- **Handle Callback**: Manages the callback from GitHub after authentication.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Login User

Implements user login via GitHub OAuth, initiating the authentication process.

```python
from fastapi import APIRouter
from apps.server.app.routes.auth import login

router = APIRouter()

@router.post("/login")
async def user_login():
    return await login()
```

### Handle Callback

Manages the callback from GitHub after authentication, processing the received data.

```python
from fastapi import APIRouter
from apps.server.app.routes.auth import callback

router = APIRouter()

@router.get("/callback")
async def github_callback():
    return await callback()
```

## When to Use

- When integrating GitHub OAuth for user authentication.
- When implementing JWT validation for secure API access.

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
client_id = "your_client_id"
client_secret = "your_client_secret"
```
<!-- L3:END -->