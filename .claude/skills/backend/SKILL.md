---
name: backend-layer
description: >
  This layer encompasses the backend services for the RepoForge application, primarily built with FastAPI.
  Trigger: When working in backend/ — adding, modifying, or debugging backend services.
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
# backend-layer

This skill covers the backend services for the RepoForge application.

**Trigger**: When working in backend/ — adding, modifying, or debugging backend services.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Configure logging | `from apps.server.app.middleware.logging_config import configure_logging` |

## Critical Patterns (Summary)
- **Middleware Configuration**: Use custom middleware for request handling and logging.
- **JWT Authentication**: Implement JWT for secure user authentication.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Middleware Configuration

Use custom middleware to handle requests, logging, and security headers effectively.

```python
# Example of middleware usage
from apps.server.app.main import request_logging_middleware

app.add_middleware(request_logging_middleware)
```

### JWT Authentication

Implement JWT for secure user authentication in FastAPI applications.

```python
# Example of JWT authentication
from apps.server.app.middleware.auth import get_current_user

@app.get("/users/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
```

## When to Use

- When implementing request logging and security features.
- When managing user authentication and authorization.

## Commands

```bash
# Run the FastAPI application
uvicorn apps.server.app.main:app --reload
```

## Anti-Patterns

### Don't: Change middleware without testing

Changing middleware can break request handling and logging, leading to security vulnerabilities.

```python
# BAD
app.add_middleware(SomeNewMiddleware)  # Without proper testing
```
<!-- L3:END -->