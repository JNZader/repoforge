---
name: generate-github-oauth-state
description: >
  This skill covers generating and validating OAuth states for GitHub authentication.
  Trigger: Load this skill when implementing GitHub OAuth flows.
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
# generate-github-oauth-state

This skill covers generating and validating OAuth states for GitHub authentication.

**Trigger**: Load this skill when implementing GitHub OAuth flows.
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

This pattern generates a unique state parameter for OAuth requests to prevent CSRF attacks.

```python
from apps.server.app.services.github_oauth import generate_state

state = generate_state()
```

### Validate OAuth state

This pattern validates the state parameter received in the callback to ensure it matches the original.

```python
from apps.server.app.services.github_oauth import validate_state

is_valid = validate_state(received_state, original_state)
```

## When to Use

- When initiating a GitHub OAuth flow to ensure security.
- When handling the callback from GitHub to verify the state.

## Commands

```bash
python -m apps.server.app.services.github_oauth
```

## Anti-Patterns

### Don't: Ignore state validation

Not validating the state can lead to security vulnerabilities such as CSRF attacks.

```python
# BAD
# Missing state validation
if received_state != original_state:
    # Handle error
```
<!-- L3:END -->