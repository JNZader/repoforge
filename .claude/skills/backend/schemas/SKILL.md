---
name: add-schemas-endpoint
description: >
  This skill covers the creation of Pydantic schemas for API request and response handling.
  Trigger: Load this skill when defining schemas for the RepoForge Web API.
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
# add-schemas-endpoint

This skill covers the creation of Pydantic schemas for API request and response handling.

**Trigger**: Load this skill when defining schemas for the RepoForge Web API.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Create User Info Schema | `UserInfo` |
| Define Token Response Schema | `TokenResponse` |

## Critical Patterns (Summary)
- **UserInfo**: Defines the schema for user information.
- **TokenResponse**: Represents the structure of the token response.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### UserInfo

Defines the schema for user information, ensuring data validation and serialization.

```python
from apps.server.app.models.schemas import UserInfo

user_info = UserInfo(username="john_doe", email="john@example.com")
```

### TokenResponse

Represents the structure of the token response, including access and refresh tokens.

```python
from apps.server.app.models.schemas import TokenResponse

token_response = TokenResponse(access_token="abc123", refresh_token="xyz456")
```

## When to Use

- When creating schemas for user-related data in the API.
- When defining responses for authentication endpoints.

## Commands

```bash
docker-compose up
python repoforge/cli.py run
```

## Anti-Patterns

### Don't: Use Plain Dictionaries for Schemas

Using plain dictionaries bypasses validation and serialization features provided by Pydantic.

```python
# BAD
user_info = {"username": "john_doe", "email": "john@example.com"}
```
<!-- L3:END -->