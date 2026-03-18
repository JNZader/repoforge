---
name: backend-layer
description: >
  This layer owns the backend services for the RepoForge project, providing a FastAPI application and middleware for authentication, logging, and rate limiting.
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

This skill covers the backend services for the RepoForge project.

**Trigger**: When working in backend/ directory and its main responsibility.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Configure application settings | `from apps.server.app.config import Settings` |

## Critical Patterns (Summary)
- **Middleware Configuration**: Use custom middleware for logging, authentication, and rate limiting.
- **Migration Management**: Handle database migrations using Alembic for version control.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Middleware Configuration

Use custom middleware to manage cross-cutting concerns like logging and authentication.

```python
# Example of middleware usage
from apps.server.app.middleware.logging_config import configure_logging
from apps.server.app.middleware.auth import get_current_user
```

### Migration Management

Handle database migrations using Alembic to ensure the database schema is up-to-date.

```python
# Example of running migrations
from apps.server.alembic.env import run_migrations_online
```

## When to Use

- When implementing new features that require backend services.
- When integrating with the frontend layer to ensure data flow.

## Commands

```bash
# Run the FastAPI application
uvicorn apps.server.app.main:app --reload

# Run database migrations
alembic upgrade head
```

## Anti-Patterns

### Don't: Change middleware without testing

Modifying middleware can break authentication or logging, leading to security issues.

```python
# BAD
# Removing essential middleware without understanding its impact
```
<!-- L3:END -->