---
name: test-security-fixtures
description: >
  This skill covers patterns for testing security using crafted fixtures.
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

This skill covers patterns for testing security using crafted fixtures.

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
- **Vulnerability Scanner**: Execute a security scan on the application.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Get Users for Testing

This pattern retrieves user data to be used in security tests.

```python
# Example of retrieving users
users = get_users()
```

### Vulnerability Scanner

This pattern executes a security scan to identify potential vulnerabilities.

```python
# Example of running the scanner
results = scanner()
```

## When to Use

- When setting up tests for user authentication and authorization.
- When validating security measures against known vulnerabilities.

## Commands

```bash
pytest tests/test_security.py
```

## Anti-Patterns

### Don't: Hardcode Sensitive Data

Hardcoding sensitive data can lead to security breaches and is against best practices.

```python
# BAD
username = "admin"
password = "password123"
```
<!-- L3:END -->