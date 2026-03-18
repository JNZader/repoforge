---
name: add-schemas-endpoint
description: >
  This skill covers the creation of Pydantic schemas for the RepoForge Web API.
  Trigger: Load this skill when defining schemas for API requests and responses.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: low
  token_estimate: 350
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# add-schemas-endpoint

This skill covers the creation of Pydantic schemas for the RepoForge Web API.

**Trigger**: Load this skill when defining schemas for API requests and responses.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Define user information schema | `UserInfo` |
| Create authentication validation response | `AuthValidateResponse` |

## Critical Patterns (Summary)
- **UserInfo**: Defines the structure for user information in requests.
- **AuthValidateResponse**: Specifies the response format for authentication validation.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### UserInfo

Defines the structure for user information in requests, ensuring data validation and type safety.

```python
from apps.server.app.models.schemas import UserInfo

user_info = UserInfo(username="john_doe", email="john@example.com")
```

### AuthValidateResponse

Specifies the response format for authentication validation, including user details and status.

```python
from apps.server.app.models.schemas import AuthValidateResponse

response = AuthValidateResponse(user=UserInfo(username="john_doe", email="john@example.com"), valid=True)
```

## When to Use

- When creating API endpoints that require user data validation.
- When handling authentication responses in the web API.

## Commands

```bash
python -m apps.server.app.main
```

## Anti-Patterns

### Don't: Use unvalidated data models

Using unvalidated data models can lead to runtime errors and security vulnerabilities.

```python
# BAD
from apps.server.app.models.schemas import UserInfo

user_info = UserInfo(username="john_doe", email="not-an-email")
```
<!-- L3:END -->