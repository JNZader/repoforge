---
name: define-request-response-schemas
description: >
  This skill covers the creation of Pydantic v2 request and response schemas.
  Trigger: Load when defining schemas for the RepoForge Web API.
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
# define-request-response-schemas

This skill covers the creation of Pydantic v2 request and response schemas.

**Trigger**: Load when defining schemas for the RepoForge Web API.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Define user info schema | `UserInfo` |
| Create token response schema | `TokenResponse` |

## Critical Patterns (Summary)
- **UserInfo**: Defines the schema for user information.
- **TokenResponse**: Creates a schema for token responses.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### UserInfo

Defines the schema for user information, ensuring all required fields are validated.

```python
from apps.server.app.models.schemas import UserInfo

user_info = UserInfo(username="john_doe", email="john@example.com")
```

### TokenResponse

Creates a schema for token responses, encapsulating the token and its expiration.

```python
from apps.server.app.models.schemas import TokenResponse

token_response = TokenResponse(access_token="abc123", token_type="bearer")
```

## When to Use

- When creating user-related API endpoints that require validation.
- When handling authentication responses in the API.

## Commands

```bash
python -m apps.server.app.main
```

## Anti-Patterns

### Don't: Use unvalidated data

Using unvalidated data can lead to security vulnerabilities and application errors.

```python
# BAD
user_info = UserInfo(username="john_doe", email="not-an-email")
```
<!-- L3:END -->