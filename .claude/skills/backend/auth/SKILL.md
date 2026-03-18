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
|--------------------|--------------------------|
| User login         | `login`                  |
| OAuth callback     | `callback`               |
| Validate JWT token | `validate_token`         |
| User logout        | `logout`                 |

## Critical Patterns (Summary)
- **User Login**: Implements the login functionality using GitHub OAuth.
- **Token Validation**: Validates JWT tokens for authenticated requests.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### User Login

Implements the login functionality using GitHub OAuth.

```python
from fastapi import APIRouter
from apps.server.app.routes.auth import login

router = APIRouter()

@router.post("/login")
async def user_login():
    return await login()
```

### Token Validation

Validates JWT tokens for authenticated requests.

```python
from fastapi import Depends
from apps.server.app.routes.auth import validate_token

async def get_current_user(token: str = Depends(validate_token)):
    return token
```

## When to Use

- When implementing user authentication via OAuth.
- When validating JWT tokens for secure API access.

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