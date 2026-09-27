---
name: add-auth-routes
description: >
  Authentication routes: GitHub OAuth login/callback, JWT validate, logout.
  Trigger: when initializing auth flow with login, callback, validate_token, logout.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: medium
token_estimate: 450
dependencies: []
related_skills: [github-oauth, jwt-validation]
load_priority: high
---

<!-- L1:START -->
# add-auth-routes

One sentence: Handles GitHub OAuth login/callback, JWT validation, and logout for the auth layer.

**Trigger**: when initializing auth flow with login, callback, validate_token, logout.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Login | `login(request)` |
| Validate | `validate_token(request, current_user)` |
| Logout | `logout(request, current_user)` |

## Critical Patterns (Summary)
- **login**: Initiates GitHub OAuth flow via redirect
- **validate_token**: Verifies JWT and attaches `current_user` to request state
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### login

Initiates GitHub OAuth flow by redirecting to the authorization URL. Uses the `login` export from `apps/server/app/routes/auth.py` to generate the redirect response.

```python
// Real code using actual exported names from this module
from fastapi import Request
from fastapi.responses import RedirectResponse
from apps.server.app.routes.auth import login

@app.get("/auth/login")
async def auth_login(request: Request) -> RedirectResponse:
    return await login(request)
```

### validate_token

Validates the JWT token from the request and retrieves the current user. Uses the `validate_token` export from `apps/server/app/routes/auth.py` to verify the token and attach the user to the request state.

```python
// Real code using actual exported names from this module
from fastapi import Request
from apps.server.app.routes.auth import validate_token
from apps.server.app.main import, &




s...










1. 1.1 1.1 1.1 1.1 1.1 1.1 1.1 1.1 1.1 1.1 1.1 1.1 1.1 1.1 1.1 1.1 