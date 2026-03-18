---
name: add-auth-endpoint
description: >
  This skill covers the implementation of authentication routes.
  Trigger: When setting up auth-related endpoints in the backend.
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
- **User login**: Handles user authentication via GitHub OAuth.
- **JWT validation**: Validates the JWT token for secure access.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### User login

Handles user authentication via GitHub OAuth.

```python
from apps.server.app.routes.auth import login

@app.post("/login")
async def login_user(credentials: OAuth2PasswordRequestForm = Depends()):
    return await login(credentials)
```

### JWT validation

Validates the JWT token for secure access.

```python
from apps.server.app.routes.auth import validate_token

@app.get("/validate")
async def validate_user(token: str):
    return await validate_token(token)
```

## When to Use

- When implementing user authentication in a FastAPI application.
- When needing to validate JWT tokens for protected routes.

## Commands

```bash
python -m uvicorn apps.server.app.main:app --reload
```

## Anti-Patterns

### Don't: Hardcode secrets

Hardcoding secrets can lead to security vulnerabilities.

```python
# BAD
SECRET_KEY = "mysecretkey"
```
<!-- L3:END -->