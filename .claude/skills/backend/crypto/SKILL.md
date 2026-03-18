---
name: encrypt-api-keys
description: >
  This skill covers AES-256-GCM encryption for provider API keys.
  Trigger: Load this skill when handling sensitive API key encryption.
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
# encrypt-api-keys

This skill covers AES-256-GCM encryption for provider API keys.

**Trigger**: Load this skill when handling sensitive API key encryption.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Derive user key | `derive_user_key` |
| Encrypt API key | `encrypt_key` |

## Critical Patterns (Summary)
- **Derive User Key**: Generate a secure key for user-specific encryption.
- **Encrypt API Key**: Securely encrypt an API key using AES-256-GCM.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Derive User Key

Generate a secure key for user-specific encryption using a password and salt.

```python
from apps.server.app.services.crypto import derive_user_key

user_key = derive_user_key(password="user_password", salt="unique_salt")
```

### Encrypt API Key

Securely encrypt an API key using AES-256-GCM for safe storage.

```python
from apps.server.app.services.crypto import encrypt_key

encrypted_key = encrypt_key(api_key="my_secret_api_key", user_key=user_key)
```

## When to Use

- When storing sensitive API keys securely.
- When transmitting API keys over insecure channels.

## Commands

```bash
python -m apps.server.app.services.crypto
```

## Anti-Patterns

### Don't: Hardcode API Keys

Hardcoding API keys in the source code exposes them to security risks.

```python
# BAD
api_key = "my_secret_api_key"
```
<!-- L3:END -->