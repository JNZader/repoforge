---
name: add-auth-endpoint
description: >
  This skill covers the implementation of authentication routes.
  Trigger: When setting up auth functionality in the backend.
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

**Trigger**: When setting up auth functionality in the backend.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task               | Pattern                     |
|--------------------|-----------------------------|
| Login user         | `login`                     |
| Handle callback    | `callback`                  |
| Validate token     | `validate_token`            |
| Logout user        | `logout`                    |

## Critical Patterns (Summary)
- **Login User**: Handles user login via GitHub OAuth.
- **Handle Callback**: Manages the callback from GitHub after authentication.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Login User

Handles user login via GitHub OAuth, initiating the authentication process.

```python
from apps.server.app.routes.auth import login

@app.post("/login")
async def login_user(credentials: OAuth2PasswordRequestForm = Depends()):
    return await login(credentials)
```

### Handle Callback

Manages the callback from GitHub after authentication, processing the received data.

```python
from apps.server.app.routes.auth import callback

@app.get("/callback")
async def github_callback(code: str):
    return await callback(code)
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

### Don't: Hardcode Secrets

Hardcoding secrets is insecure and exposes sensitive information.

```python
# BAD
client_id = "your_client_id"
client_secret = "your_client_secret"
```
<!-- L3:END -->