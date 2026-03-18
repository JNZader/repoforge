---
name: generate-github-oauth-state
description: >
  This skill covers generating and validating GitHub OAuth states.
  Trigger: When implementing GitHub OAuth in your application.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: low
  token_estimate: 250
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# Generate GitHub OAuth State

This skill covers generating and validating GitHub OAuth states.

**Trigger**: When implementing GitHub OAuth in your application.
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

This pattern generates a unique state string for OAuth requests to prevent CSRF attacks.

```python
from apps.server.app.services.github_oauth import generate_state

state = generate_state()
```

### Validate OAuth state

This pattern validates the state received in the callback to ensure it matches the original state.

```python
from apps.server.app.services.github_oauth import validate_state

is_valid = validate_state(received_state, original_state)
```

## When to Use

- When initiating a GitHub OAuth flow to ensure security.
- When handling the callback to verify the integrity of the request.

## Commands

```bash
python -m apps.server.app.services.github_oauth
```

## Anti-Patterns

### Don't: Use static state values

Using static values for state can lead to security vulnerabilities.

```python
# BAD
state = "static_value"
```
<!-- L3:END -->