---
name: generate-github-oauth-state
description: >
  This skill covers GitHub OAuth helper functions for state management and user retrieval.
  Trigger: Load this skill when implementing GitHub OAuth in your application.
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
# generate-github-oauth-state

This skill covers GitHub OAuth helper functions for state management and user retrieval.

**Trigger**: Load this skill when implementing GitHub OAuth in your application.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Generate OAuth state | `generate_state()` |
| Validate OAuth state | `validate_state()` |
| Exchange code for token | `exchange_code_for_token()` |
| Get GitHub user | `get_github_user()` |

## Critical Patterns (Summary)
- **Generate OAuth state**: Create a unique state parameter for OAuth flow.
- **Validate OAuth state**: Ensure the state parameter matches the expected value.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Generate OAuth state

This function generates a unique state parameter to prevent CSRF attacks during the OAuth flow.

```python
from apps.server.app.services.github_oauth import generate_state

state = generate_state()
```

### Validate OAuth state

This function checks if the provided state matches the expected value to ensure the integrity of the OAuth process.

```python
from apps.server.app.services.github_oauth import validate_state

is_valid = validate_state(received_state, expected_state)
```

## When to Use

- When initiating the GitHub OAuth flow to generate a state parameter.
- When handling the callback from GitHub to validate the state parameter.

## Commands

```bash
python -m apps.server.app.services.github_oauth
```

## Anti-Patterns

### Don't: Use static state values

Using static state values can lead to security vulnerabilities such as CSRF attacks.

```python
# BAD
state = "static_value"
```
<!-- L3:END -->