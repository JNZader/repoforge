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
- **User Info Schema**: Defines the structure for user information in requests.
- **Token Response Schema**: Specifies the format for token responses from the API.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### User Info Schema

Defines the structure for user information in requests, ensuring data validation and serialization.

```python
from apps.server.app.models.schemas import UserInfo

user_info = UserInfo(username="john_doe", email="john@example.com")
```

### Token Response Schema

Specifies the format for token responses from the API, including necessary fields for authentication.

```python
from apps.server.app.models.schemas import TokenResponse

token_response = TokenResponse(access_token="abc123", token_type="bearer")
```

## When to Use

- When creating API endpoints that require user data validation.
- When handling authentication responses in the web API.

## Commands

```bash
docker-compose up
python repoforge/cli.py run
```

## Anti-Patterns

### Don't: Use Inconsistent Schema Definitions

Using inconsistent schema definitions can lead to validation errors and unexpected behavior.

```python
# BAD
from apps.server.app.models.schemas import UserInfo

user_info = UserInfo(username="john_doe", email=123)  # email should be a string
```
<!-- L3:END -->