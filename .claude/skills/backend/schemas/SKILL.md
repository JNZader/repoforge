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
# Define Request/Response Schemas

This skill covers the creation of Pydantic v2 request and response schemas.

**Trigger**: Load this skill when defining schemas for the RepoForge Web API.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Define user information schema | `UserInfo` |
| Create token response schema | `TokenResponse` |

## Critical Patterns (Summary)
- **UserInfo**: Defines the schema for user information.
- **TokenResponse**: Creates a schema for the token response.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### UserInfo

Defines the schema for user information, ensuring all required fields are validated.

```python
from apps.server.app.models.schemas import UserInfo

user_info = UserInfo(username="john_doe", email="john@example.com", full_name="John Doe")
```

### TokenResponse

Creates a schema for the token response, encapsulating the necessary fields for authentication.

```python
from apps.server.app.models.schemas import TokenResponse

token_response = TokenResponse(access_token="abc123", token_type="bearer")
```

## When to Use

- When defining schemas for user-related data in the API.
- When creating responses for authentication endpoints.

## Commands

```bash
python -m apps.server.app.main
```

## Anti-Patterns

### Don't: Use unvalidated data

Using unvalidated data can lead to security vulnerabilities and data integrity issues.

```python
# BAD
user_info = UserInfo(username="john_doe", email="invalid_email", full_name="John Doe")
```
<!-- L3:END -->