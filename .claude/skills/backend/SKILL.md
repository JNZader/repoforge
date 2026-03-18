---
name: backend-layer
description: >
  This layer provides the backend services for the RepoForge application, utilizing FastAPI for web services and Alembic for database migrations.
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

This skill covers the backend services of the RepoForge application.

**Trigger**: When working in backend/ directory and its main responsibility is to manage backend services.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Configure application settings | `from apps.server.app.config import Settings` |

## Critical Patterns (Summary)
- **Middleware Configuration**: Use custom middleware for logging and authentication.
- **Database Migration**: Utilize Alembic for managing database schema changes.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Middleware Configuration

Use custom middleware to handle cross-cutting concerns like logging and authentication.

```python
# Example of middleware usage
from apps.server.app.middleware.logging_config import configure_logging
from apps.server.app.middleware.auth import get_current_user
```

### Database Migration Management

Utilize Alembic for managing database migrations, ensuring schema changes are applied consistently.

```python
# Example of running migrations
from apps.server.alembic.env import run_migrations_online
```

## When to Use

- When implementing new API endpoints that require authentication.
- When modifying the database schema and needing to apply migrations.

## Commands

```bash
# To run the FastAPI application
uvicorn apps.server.app.main:app --reload

# To run database migrations
alembic upgrade head
```

## Anti-Patterns

### Don't: Change middleware without testing

Changing middleware can break authentication or logging, leading to security issues or loss of important logs.

```python
# BAD
# Removing authentication middleware without proper testing
```
<!-- L3:END -->