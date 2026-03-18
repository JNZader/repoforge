---
name: define-request-response-schemas
description: >
  This skill covers the creation of Pydantic v2 request and response schemas.
  Trigger: Load this skill when defining schemas for the RepoForge Web API.
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
# Define Request and Response Schemas

This skill covers the creation of Pydantic v2 request and response schemas.

**Trigger**: Load this skill when defining schemas for the RepoForge Web API.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Define User Info Schema | `UserInfo` |
| Create Token Response Schema | `TokenResponse` |

## Critical Patterns (Summary)
- **Define User Info Schema**: Create a schema for user information using `UserInfo`.
- **Create Token Response Schema**: Define a schema for token responses with `TokenResponse`.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Define User Info Schema

This pattern defines a schema for user information using the `UserInfo` model.

```python
from apps.server.app.models.schemas import UserInfo

user_info = UserInfo(username="john_doe", email="john@example.com", full_name="John Doe")
```

### Create Token Response Schema

This pattern creates a schema for token responses using the `TokenResponse` model.

```python
from apps.server.app.models.schemas import TokenResponse

token_response = TokenResponse(access_token="abc123", token_type="bearer")
```

## When to Use

- When creating user-related API endpoints that require user information.
- When implementing authentication mechanisms that return tokens.

## Commands

```bash
docker-compose run app python repoforge/cli.py
```

## Anti-Patterns

### Don't: Use Inconsistent Schema Fields

Using inconsistent field names across schemas can lead to confusion and errors.

```python
# BAD
from apps.server.app.models.schemas import UserInfo

user_info = UserInfo(user_name="john_doe", email="john@example.com")  # Inconsistent field name
```
<!-- L3:END -->