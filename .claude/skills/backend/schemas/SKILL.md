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
| Create User Info Schema | `UserInfo` |
| Create User Response Schema | `UserResponse` |

## Critical Patterns (Summary)
- **Create User Info Schema**: Defines the structure for user information.
- **Create User Response Schema**: Specifies the response format for user-related requests.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Create User Info Schema

Defines the structure for user information using Pydantic.

```python
from apps.server.app.models.schemas import UserInfo

user_info = UserInfo(username="john_doe", email="john@example.com", full_name="John Doe")
```

### Create User Response Schema

Specifies the response format for user-related requests.

```python
from apps.server.app.models.schemas import UserResponse

user_response = UserResponse(user_id="12345", username="john_doe", email="john@example.com")
```

## When to Use

- When creating API endpoints that require user information validation.
- When defining response formats for user-related API calls.

## Commands

```bash
python -m apps.server.app.main
```

## Anti-Patterns

### Don't: Use Inconsistent Schema Fields

Using inconsistent field names across schemas can lead to confusion and errors.

```python
# BAD
from apps.server.app.models.schemas import UserInfo

user_info = UserInfo(user_name="john_doe", email_address="john@example.com")  # Inconsistent field names
```
<!-- L3:END -->