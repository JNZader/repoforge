---
name: backend-layer
description: >
  This layer encompasses the backend services for the RepoForge project, primarily built with FastAPI.
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

**Trigger**: When working in backend/ directory and its main responsibility is to manage backend services.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Configure logging | `from apps.server.app.middleware.logging_config import configure_logging` |

## Critical Patterns (Summary)
- **Middleware Configuration**: Use custom middleware for logging, authentication, and rate limiting.
- **Migration Management**: Handle database migrations using Alembic for schema changes.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Middleware Configuration

Utilize middleware to manage cross-cutting concerns like logging and authentication.

```python
# Example of logging middleware
from apps.server.app.middleware.logging_config import configure_logging
```

### Migration Management

Use Alembic for managing database migrations, ensuring schema consistency across environments.

```python
# Example of running migrations
from apps.server.alembic.env import run_migrations_online
```

## When to Use

- When implementing new API endpoints that require authentication.
- When configuring logging for better observability in the backend.

## Commands

```bash
# Run the FastAPI server
uvicorn apps.server.app.main:app --reload

# Run migrations
alembic upgrade head
```

## Anti-Patterns

### Don't: Modify middleware without testing

Changing middleware can lead to unexpected behavior in authentication or logging.

```python
# BAD
# Removing essential logging middleware without testing
```
<!-- L3:END -->