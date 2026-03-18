---
name: add-schemas-endpoint
description: >
  This skill covers the creation of Pydantic schemas for the RepoForge Web API.
  Trigger: Load this skill when defining schemas for API requests and responses.
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
- **UserInfo**: Defines the structure for user information in requests.
- **UserResponse**: Specifies the response format for user-related API calls.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### UserInfo

Defines the structure for user information in requests, ensuring data validation and type safety.

```python
from apps.server.app.models.schemas import UserInfo

user_info = UserInfo(username="john_doe", email="john@example.com")
```

### UserResponse

Specifies the response format for user-related API calls, encapsulating user data and metadata.

```python
from apps.server.app.models.schemas import UserResponse

user_response = UserResponse(user_id="123", username="john_doe", email="john@example.com")
```

## When to Use

- When creating API endpoints that require user data validation.
- When defining response formats for user-related API interactions.

## Commands

```bash
docker-compose up
python repoforge/cli.py run
```

## Anti-Patterns

### Don't: Use Unvalidated Data

Using unvalidated data can lead to runtime errors and security vulnerabilities.

```python
# BAD
user_info = UserInfo(username="john_doe", email="not-an-email")
```
<!-- L3:END -->