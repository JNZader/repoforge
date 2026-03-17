---
name: test-security-fixtures
description: >
  This skill covers patterns for testing security using crafted content.
  Trigger: test_security.
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
# test-security-fixtures

This skill covers patterns for testing security using crafted content.

**Trigger**: test_security.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Get users for testing | `get_users()` |
| Scan for vulnerabilities | `scanner()` |

## Critical Patterns (Summary)
- **Get Users**: Retrieve user data for security tests.
- **Vulnerability Scanner**: Execute a scan to identify security issues.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Get Users for Testing

This pattern retrieves user data that can be used in security tests.

```python
# Example of retrieving users
users = get_users()
```

### Vulnerability Scanner

This pattern executes a scan to identify potential security vulnerabilities in the application.

```python
# Example of running the scanner
results = scanner()
```

## When to Use

- When you need user data for security testing scenarios.
- When scanning your application for vulnerabilities before deployment.

## Commands

```bash
pytest tests/test_security.py
```

## Anti-Patterns

### Don't: Hardcode User Data

Hardcoding user data can lead to security risks and unmaintainable tests.

```python
# BAD
users = [{"username": "admin", "password": "1234"}]
```
<!-- L3:END -->