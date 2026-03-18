---
name: backend-layer
description: >
  This layer encompasses the backend services for the RepoForge project, primarily built with FastAPI and async database interactions.
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
| Initialize FastAPI app | `from apps.server.app.main import lifespan` |

## Critical Patterns (Summary)
- **Middleware Usage**: Implement custom middleware for request handling.
- **Database Session Management**: Use async database sessions for efficient data access.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Middleware Usage

Implement custom middleware to handle cross-cutting concerns like logging and authentication.

```python
# Example of middleware usage
from apps.server.app.main import request_logging_middleware
```

### Database Session Management

Utilize async database sessions to ensure non-blocking database operations.

```python
# Example of database session management
from apps.server.app.models.database import get_db
```

## When to Use

- When implementing new API endpoints that require authentication.
- When setting up database interactions for new models.

## Commands

```bash
# Run migrations
python apps/server/alembic/env.py run_migrations_online
# Start FastAPI server
uvicorn apps.server.app.main:app --reload
```

## Anti-Patterns

### Don't: Modify database models without migration

Changing database models directly can lead to inconsistencies and data loss.

```python
# BAD
# Directly modifying models without running migrations
```
<!-- L3:END -->