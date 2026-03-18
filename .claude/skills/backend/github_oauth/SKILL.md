---
name: generate-github-oauth-state
description: >
  This skill covers generating and validating OAuth states for GitHub authentication.
  Trigger: Load this skill when implementing GitHub OAuth in your application.
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
# generate-github-oauth-state

This skill covers generating and validating OAuth states for GitHub authentication.

**Trigger**: Load this skill when implementing GitHub OAuth in your application.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Generate OAuth state | `generate_state()` |
| Validate OAuth state | `validate_state()` |

## Critical Patterns (Summary)
- **Generate OAuth state**: Use `generate_state()` to create a unique state parameter.
- **Validate OAuth state**: Use `validate_state()` to ensure the state matches during the callback.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Generate OAuth state

Use `generate_state()` to create a unique state parameter for OAuth requests, ensuring security against CSRF attacks.

```python
from apps.server.app.services.github_oauth import generate_state

state = generate_state()
```

### Validate OAuth state

Use `validate_state()` to check if the state parameter received in the callback matches the one generated, preventing CSRF attacks.

```python
from apps.server.app.services.github_oauth import validate_state

is_valid = validate_state(received_state, expected_state)
```

## When to Use

- When initiating a GitHub OAuth flow to ensure a unique state is generated.
- When handling the callback from GitHub to validate the state parameter.

## Commands

```bash
docker-compose run app python apps/server/app/main.py
```

## Anti-Patterns

### Don't: Ignore state validation

Ignoring state validation can lead to security vulnerabilities such as CSRF attacks.

```python
# BAD
# Not validating the state parameter
if received_state != expected_state:
    # Handle error
```
<!-- L3:END -->