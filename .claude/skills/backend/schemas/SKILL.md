---
name: add-schemas-model
description: >
  Pydantic v2 schemas for RepoForge API requests and responses.
  Trigger: when working with schemas in the backend.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills:
  - define-pydantic-models
  - handle-auth-responses
load_priority: high
---

<!-- L1:START -->
# add-schemas-model

Defines and validates the core request/response models for the RepoForge API.

**Trigger**: when working with schemas in the backend.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Return user info | `UserResponse(user=UserInfo(...))` |
| Validate generation input | `GenerateRequest(**payload)` |
| Emit token response | `TokenResponse(access_token=token)` |

## Critical Patterns (Summary)
- **UserResponse schema**: Wrap `UserInfo` in a response model for API output.
- **GenerateRequest validation**: Use the request schema to enforce payload structure.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### UserResponse schema

Encapsulate user details in a dedicated response model to keep API contracts explicit.

```python
from apps.server.app.models.schemas import UserInfo, UserResponse

def get_current_user(user_id: str) -> UserResponse:
    info = UserInfo(id=user_id, name="Alice", email="alice@example.com")
    return UserResponse(user=info)
```

### GenerateRequest validation

Leverage `GenerateRequest` to automatically validate incoming generation payloads, ensuring correct types and defaults.

```python
from apps.server.app.models.schemas import GenerateRequest, GenerateResponse

def start_generation(payload: dict) -> GenerateResponse:
    req = GenerateRequest(**payload)          # raises ValidationError on bad data
    # process request...
    return GenerateResponse(job_id=req.job_id, status="queued")
```

## When to Use

- When returning user data from any endpoint.
- When accepting generation parameters from clients.
- When needing a typed token payload for authentication flows.

## Commands

```bash
docker compose up -d            # start the RepoForge services
python -m apps.server.app.main  # run the FastAPI server locally
```

## Anti-Patterns

### Don't: Use mutable defaults in Pydantic models

Mutable defaults (e.g., `list = []`) are shared across instances, causing unexpected state leakage.

```python
from pydantic import BaseModel

class BadModel(BaseModel):
    tags: list = []  # BAD: mutable default
```
<!-- L3:END -->