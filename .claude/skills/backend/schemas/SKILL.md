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
| Define user info schema | `UserInfo` |
| Create token response schema | `TokenResponse` |

## Critical Patterns (Summary)
- **User Info Schema**: Defines the structure for user information.
- **Token Response Schema**: Specifies the format for token responses.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### User Info Schema

Defines the structure for user information using Pydantic.

```python
from apps.server.app.models.schemas import UserInfo

user_info = UserInfo(username="john_doe", email="john@example.com")
```

### Token Response Schema

Specifies the format for token responses, ensuring proper validation.

```python
from apps.server.app.models.schemas import TokenResponse

token_response = TokenResponse(access_token="abc123", token_type="bearer")
```

## When to Use

- When creating API endpoints that require user information validation.
- When handling authentication responses in the RepoForge Web API.

## Commands

```bash
docker-compose up
python repoforge/cli.py run
```

## Anti-Patterns

### Don't: Use Unvalidated Data

Using unvalidated data can lead to security vulnerabilities and data integrity issues.

```python
# BAD
user_info = UserInfo(username="john_doe", email="not-an-email")
```
<!-- L3:END -->