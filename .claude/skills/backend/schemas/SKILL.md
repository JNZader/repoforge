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
- **Token Response Schema**: Specifies the format of the token response from authentication.
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

Specifies the format of the token response from authentication, including necessary fields.

```python
from apps.server.app.models.schemas import TokenResponse

token_response = TokenResponse(access_token="abc123", token_type="bearer")
```

## When to Use

- When creating request validation for user-related endpoints.
- When defining responses for authentication processes.

## Commands

```bash
docker-compose run app python repoforge/cli.py
```

## Anti-Patterns

### Don't: Use Unvalidated Data

Using unvalidated data can lead to security vulnerabilities and application errors.

```python
# BAD
user_info = UserInfo(username="john_doe", email="not-an-email")
```
<!-- L3:END -->