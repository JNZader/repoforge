---
name: add-schemas-endpoint
description: >
  This skill covers the creation of Pydantic schemas for API requests and responses.
  Trigger: Load this skill when defining schemas for the RepoForge Web API.
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

This skill covers the creation of Pydantic schemas for API requests and responses.

**Trigger**: Load this skill when defining schemas for the RepoForge Web API.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Create User Response Schema | `UserResponse` |
| Validate Authentication Request | `AuthValidateResponse` |

## Critical Patterns (Summary)
- **Create User Response Schema**: Defines the structure for user response data.
- **Validate Authentication Request**: Validates the structure of authentication requests.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Create User Response Schema

Defines the structure for user response data using Pydantic.

```python
from apps.server.app.models.schemas import UserResponse

user_response = UserResponse(username="john_doe", email="john@example.com")
```

### Validate Authentication Request

Validates the structure of authentication requests to ensure required fields are present.

```python
from apps.server.app.models.schemas import AuthValidateResponse

auth_response = AuthValidateResponse(is_valid=True, user_id="12345")
```

## When to Use

- When creating API endpoints that require structured user data.
- When validating incoming authentication requests to ensure they meet the expected schema.

## Commands

```bash
python -m apps.server.app.main
```

## Anti-Patterns

### Don't: Use Unvalidated Data

Using unvalidated data can lead to security vulnerabilities and application errors.

```python
# BAD
user_response = UserResponse(username="john_doe", email=None)  # Missing required field
```
<!-- L3:END -->