---
name: add-auth-endpoints
description: >
  Provides FastAPI routes for GitHub OAuth login, callback, JWT validation, and logout.
  Trigger: auth
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills:
  - configure-settings
  - manage-jwt
load_priority: high
---

<!-- L1:START -->
# add-auth-endpoints

Adds FastAPI routes for GitHub OAuth login, callback handling, JWT validation, and logout.

**Trigger**: auth
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Add login route | `login(request)` |
| Validate JWT | `validate_token(request, current_user)` |
| Add logout route | `logout(request, current_user)` |

## Critical Patterns (Summary)
- **OAuth flow**: expose `login` and `callback` to start and complete GitHub OAuth.
- **Token guard**: use `validate_token` to enforce JWT authentication on protected endpoints.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### OAuth flow with `login` and `callback`

Expose `/login` to redirect users to GitHub and `/callback` to handle the provider response.  
Both functions return `RedirectResponse` and rely on FastAPI's `Request` and query parameters.

```python
from fastapi import APIRouter, Request, Query
from fastapi.responses import RedirectResponse

router = APIRouter()

@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    # Build GitHub OAuth URL and redirect
    redirect_uri = "https://github.com/login/oauth/authorize?...your_params..."
    return RedirectResponse(url=redirect_uri)

@router.get("/callback")
async def callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    # Exchange `code` for access token, then redirect to app
    if error:
        raise HTTPException(status_code=400, detail=error)
    # token = exchange_code_for_token(code)
    return RedirectResponse(url="/")
```

### JWT validation with `validate_token`

Protect routes by extracting the current user from the JWT and returning a structured response.

```python
from fastapi import APIRouter, Request, Depends

router = APIRouter()

@router.post("/validate")
async def validate_token(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> AuthValidateResponse:
    # `current_user` is populated by JWT verification middleware
    return AuthValidateResponse(user_id=current_user.id, valid=True)
```

## When to Use

- Adding GitHub OAuth login to a new FastAPI service.
- Securing endpoints that require a verified JWT.
- Implementing a logout endpoint that clears session cookies or tokens.

## Commands

```bash
# Run the API locally
uvicorn apps.server.app.main:app --reload

# Build and start Docker containers
docker compose build
docker compose up -d

# Execute repository CLI (e.g., migrations)
python -m repoforge.cli migrate
```

## Anti-Patterns

### Don't: Return raw dict from `logout` without proper HTTP response

Returning a plain dictionary bypasses FastAPI's response handling and may expose internal data.

```python
# BAD
@router.post("/logout")
async def logout(request: Request, current_user: CurrentUser) -> dict:
    return {"message": "logged out"}  # No status code or response model
```

Instead, use a proper response type such as `JSONResponse` or a Pydantic model.
<!-- L3:END -->