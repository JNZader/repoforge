---
name: add-auth-endpoints
description: >-
  Implements GitHub OAuth login/callback and JWT validation for the auth layer.
  Trigger: when auth routes are needed.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 340
dependencies: []
related_skills:
  - add-github-oauth
  - handle-jwt
load_priority: high
---

<!-- L1:START -->
# add-auth-endpoints

Implements GitHub OAuth login, callback handling, JWT validation, and logout.

**Trigger**: when auth routes are needed.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task                     | Pattern |
|--------------------------|---------|
| Initiate GitHub login    | `login(request)` |
| Process OAuth callback   | `callback(request, code, state, error)` |
| Verify JWT token         | `validate_token(request, current_user)` |

## Critical Patterns (Summary)
- **OAuth Login Endpoint**: expose `/login` that redirects to GitHub.
- **JWT Validation Endpoint**: expose `/validate` that returns user info if token is valid.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### OAuth Login Endpoint

Expose a FastAPI route that starts the GitHub OAuth flow and redirects the client.  
Use the exported `login` function to build the redirect URL and log the attempt.

```python
from fastapi import Request
from fastapi.responses import RedirectResponse
import logging

async def login(request: Request) -> RedirectResponse:
    logging.info("Starting GitHub OAuth login")
    redirect_url = f"https://github.com/login/oauth/authorize?client_id={settings.github_client_id}"
    return RedirectResponse(url=redirect_url)
```

### JWT Validation Endpoint

Validate the incoming JWT and return a structured response.  
Leverage `validate_token` which receives the `CurrentUser` dependency and returns `AuthValidateResponse`.

```python
from fastapi import Request, Depends
from apps.server.app.schemas import AuthValidateResponse
from apps.server.app.dependencies import CurrentUser

async def validate_token(request: Request, current_user: CurrentUser) -> AuthValidateResponse:
    # FastAPI resolves CurrentUser from the JWT
    return AuthValidateResponse(user_id=current_user.id, email=current_user.email)
```

## When to Use

- Adding GitHub OAuth login to a new FastAPI service.
- Securing API endpoints with JWT validation after user authentication.
- Implementing a logout route that clears session cookies or tokens.

## Commands

```bash
# Run the API locally
uvicorn apps.server.app.main:app --reload

# Build and start containers
docker compose up -d --build

# Execute the CLI entry point
python -m repoforge.cli run
```

## Anti-Patterns

### Don't: Return raw dict from `logout` without proper response handling

Returning a plain dictionary bypasses FastAPI's response model and may expose internal data.

```python
# BAD
async def logout(request: Request, current_user: CurrentUser) -> dict:
    return {"message": "logged out"}  # no status code, no cookie clearing
```
<!-- L3:END -->