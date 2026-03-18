---
name: generate-github-oauth-state
description: >
  This skill covers generating and validating GitHub OAuth states.
  Trigger: Load this skill when implementing GitHub OAuth functionality.
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

This skill covers generating and validating GitHub OAuth states.

**Trigger**: Load this skill when implementing GitHub OAuth functionality.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Generate OAuth state | `generate_state()` |
| Validate OAuth state | `validate_state()` |

## Critical Patterns (Summary)
- **Generate OAuth state**: Use `generate_state()` to create a unique state for OAuth.
- **Validate OAuth state**: Use `validate_state()` to ensure the state matches during the callback.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Generate OAuth state

Use `generate_state()` to create a unique state for OAuth, ensuring security against CSRF attacks.

```python
from apps.server.app.services.github_oauth import generate_state

state = generate_state()
```

### Validate OAuth state

Use `validate_state()` to ensure the state matches during the callback, preventing unauthorized access.

```python
from apps.server.app.services.github_oauth import validate_state

is_valid = validate_state(received_state, expected_state)
```

## When to Use

- When initiating the OAuth flow with GitHub.
- When handling the callback from GitHub to verify the state.

## Commands

```bash
docker-compose up
python -m apps.server.app.main
```

## Anti-Patterns

### Don't: Hardcode state values

Hardcoding state values can lead to security vulnerabilities and CSRF attacks.

```python
# BAD
state = "fixed_value"
```
<!-- L3:END -->