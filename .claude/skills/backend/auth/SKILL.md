---
name: manage-auth-routes
description: >
  This skill covers patterns for managing authentication routes in a FastAPI application.
  Trigger: When implementing authentication features in the backend.
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
# manage-auth-routes

This skill covers patterns for managing authentication routes in a FastAPI application.

**Trigger**: When implementing authentication features in the backend.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task               | Pattern                     |
|--------------------|-----------------------------|
| Login user         | `login`                     |
| Handle callback    | `callback`                  |
| Validate JWT       | `validate_token`            |
| Logout user        | `logout`                    |

## Critical Patterns (Summary)
- **Login User**: Handles user login via GitHub OAuth.
- **Validate JWT**: Validates the JWT token for authenticated requests.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Login User

Handles user login via GitHub OAuth, initiating the authentication process.

```python
from apps.server.app.routes.auth import login

@app.get("/login")
async def login_user():
    return await login()
```

### Validate JWT

Validates the JWT token for authenticated requests, ensuring secure access.

```python
from apps.server.app.routes.auth import validate_token

@app.get("/protected")
async def protected_route(token: str):
    return await validate_token(token)
```

## When to Use

- When implementing user authentication via OAuth in a FastAPI application.
- When securing routes that require user validation through JWT.

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