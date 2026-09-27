---
name: add-schemas-model
description: >
  Provides patterns for defining and using Pydantic v2 request/response schemas in the RepoForge API.
  Trigger: When working with schemas for request/response validation.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills:
  - define-pydantic-models
  - handle-auth
load_priority: high
---

<!-- L1:START -->
# add-schemas-model

Defines concise, type‑safe Pydantic schemas for API payloads.

**Trigger**: When working with schemas for request/response validation.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Create user response | `class UserResponse(BaseModel): ...` |
| Return token payload | `class TokenResponse(BaseModel): ...` |
| List generations | `class GenerationListResponse(BaseModel): ...` |

## Critical Patterns (Summary)
- **UserResponse schema**: model API user data with `UserResponse`.
- **TokenResponse schema**: standardize JWT payload using `TokenResponse`.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### UserResponse schema

Encapsulate user data returned by the API in a single, validated model.

```python
from pydantic import BaseModel, Field
from uuid import UUID

class UserInfo(BaseModel):
    id: UUID
    username: str
    email: str

class UserResponse(BaseModel):
    user: UserInfo = Field(..., description="Authenticated user details")
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
```

### TokenResponse schema

Provide a consistent shape for JWT access/refresh tokens.

```python
from pydantic import BaseModel, Field
from datetime import datetime, timedelta

class TokenResponse(BaseModel):
    access_token: str = Field(..., description="Bearer token")
    token_type: str = Field(default="bearer")
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(hours=1))
```

## When to Use

- When returning user information from `/auth/me` or similar endpoints.  
- When issuing JWTs after successful authentication.  
- When serializing generation results for `/generate` responses.

## Commands

```bash
# Build and run the Docker environment
docker compose up --build -d

# Run the CLI entry point to start the server
python -m repoforge.cli serve

# Validate schemas with pytest
pytest -q apps/server/app/models/test_schemas.py
```

## Anti-Patterns

### Don't: Use mutable defaults in Pydantic models

Mutable defaults (e.g., `list = []`) bypass validation and cause shared state across instances.

```python
class BadSchema(BaseModel):
    tags: list = []  # BAD: mutable default
```
<!-- L3:END -->