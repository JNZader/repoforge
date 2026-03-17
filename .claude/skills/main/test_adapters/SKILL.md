---
name: test-adapters-strip-yaml-frontmatter
description: >
  This skill covers testing the _strip_yaml_frontmatter helper.
  Trigger: test_adapters.
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
# test-adapters-strip-yaml-frontmatter

This skill covers testing the _strip_yaml_frontmatter helper.

**Trigger**: test_adapters.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Get users | `get_users()` |
| Sample skills | `sample_skills` |

## Critical Patterns (Summary)
- **Get Users**: Retrieve user data for testing.
- **Sample Skills**: Access predefined skills for validation.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Get Users

This pattern retrieves user data for testing purposes.

```python
# Example usage of get_users
users = get_users()
```

### Sample Skills

This pattern accesses predefined skills to validate functionality.

```python
# Example usage of sample_skills
skills = sample_skills
```

## When to Use

- When validating the functionality of YAML frontmatter stripping.
- When testing user-related features in the application.

## Commands

```bash
pytest tests/test_adapters.py
```

## Anti-Patterns

### Don't: Ignore Test Coverage

Neglecting test coverage can lead to untested code paths.

```python
# BAD
def unused_function():
    pass
```
<!-- L3:END -->