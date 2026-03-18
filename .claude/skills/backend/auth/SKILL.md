---
name: add-auth-endpoint
description: >
  This skill covers the implementation of authentication routes.
  Trigger: When setting up user authentication in the backend.
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

**Trigger**: When setting up user authentication in the backend.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task               | Pattern                     |
|--------------------|-----------------------------|
| User login         | `login`                     |
| OAuth callback     | `callback`                  |
| Token validation    | `validate_token`            |
| User logout        | `logout`                    |

## Critical Patterns (Summary)
- **User Login**: Handles user login via GitHub OAuth.
- **OAuth Callback**: Manages the callback from GitHub after authentication.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### User Login

Handles user login via GitHub OAuth, initiating the authentication process.

```python
from fastapi import APIRouter
from apps.server.app.routes.auth import login

router = APIRouter()

@router.post("/login")
async def user_login():
    return await login()
```

### OAuth Callback

Manages the callback from GitHub after authentication, processing the received data.

```python
from fastapi import APIRouter
from apps.server.app.routes.auth import callback

router = APIRouter()

@router.get("/callback")
async def oauth_callback():
    return await callback()
```

## When to Use

- When implementing user authentication for a web application.
- When integrating third-party OAuth providers like GitHub.

## Commands

```bash
docker-compose up
python apps/server/app/main.py
```

## Anti-Patterns

### Don't: Hardcode Secrets

Hardcoding secrets like client IDs and tokens is insecure and should be avoided.

```python
# BAD
CLIENT_ID = "your_client_id"
CLIENT_SECRET = "your_client_secret"
```
<!-- L3:END -->