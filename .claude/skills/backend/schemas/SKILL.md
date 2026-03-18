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
| Define user information schema | `UserInfo` |
| Create authentication validation response | `AuthValidateResponse` |

## Critical Patterns (Summary)
- **UserInfo**: Defines the schema for user information.
- **AuthValidateResponse**: Creates a response schema for authentication validation.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### UserInfo

Defines the schema for user information, ensuring all required fields are validated.

```python
from apps.server.app.models.schemas import UserInfo

user_info = UserInfo(username="john_doe", email="john@example.com", full_name="John Doe")
```

### AuthValidateResponse

Creates a response schema for authentication validation, encapsulating the necessary fields.

```python
from apps.server.app.models.schemas import AuthValidateResponse

auth_response = AuthValidateResponse(is_valid=True, user_id="12345")
```

## When to Use

- When creating schemas for user-related data in the API.
- When defining responses for authentication processes.

## Commands

```bash
docker-compose run app python apps/server/app/main.py
```

## Anti-Patterns

### Don't: Use unvalidated data

Using unvalidated data can lead to security vulnerabilities and data integrity issues.

```python
# BAD
user_info = UserInfo(username="john_doe", email="invalid-email", full_name="John Doe")
```
<!-- L3:END -->