---
name: add-schemas-endpoint
description: >
  Pydantic v2 request/response schemas for RepoForge Web API.
  Trigger: when defining or validating schemas
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: low
  token_estimate: 450
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# add-schemas-endpoint

Pydantic v2 request/response schemas for RepoForge Web API.

**Trigger**: when defining or validating schemas
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Validate request | `UserInfo` |
| Response model | `UserResponse` |
| Token handling | `TokenResponse` |
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Pattern: UserInfo Schema Validation

The `UserInfo` schema validates incoming user data using Pydantic v2's `model_validate` for type-safe deserialization.

```python
python
data = UserInfo.model_validate(request_json)
```

### Pattern: TokenResponse Construction

`TokenResponse` structures authentication tokens with explicit `access_token` and `expires_in` fields for consistent API responses.

```python
python
token = TokenResponse(access_token=jwt_token, expires_in=3600)
```

## When to Use

- Validating incoming request bodies against `UserInfo`
- Constructing `TokenResponse` for auth endpoints
- Serializing model instances to `UserResponse`

## Commands

```bash
docker compose up -d
python -m repoforge.cli validate-schema
```

## Anti-Patterns

### Don't: Use `dict()` for schema conversion

Directly converting Pydantic models to dict loses type validation and errors on missing fields.

```python
python
# BAD
user_dict = dict(user_model)
```
<!-- L3:END -->