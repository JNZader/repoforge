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
  token_estimate: 750
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

| Task               | Pattern                          |
|--------------------|----------------------------------|
| Run migrations      | `run_migrations_online()`        |

## Critical Patterns (Summary)
- **Migration Management**: Use Alembic for handling database migrations.
- **Middleware Setup**: Implement custom middleware for request handling.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Migration Management

Use Alembic to manage database migrations effectively, ensuring the database schema is up-to-date.

```python
# Example using real exported names
from apps.server.alembic.env import run_migrations_online

run_migrations_online()
```

### Middleware Setup

Implement custom middleware to handle authentication and logging for incoming requests.

```python
# Example
from apps.server.app.middleware.auth import get_current_user

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    user = await get_current_user(request)
    response = await call_next(request)
    return response
```

## When to Use

- When adding new database migrations.
- When implementing authentication for API endpoints.

## Commands

```bash
# Run migrations
alembic upgrade head

# Start the FastAPI server
uvicorn apps.server.app.main:app --reload
```

## Anti-Patterns

### Don't: Modify database models without migration

Changing database models directly can lead to inconsistencies and data loss.

```python
# BAD
# Directly modifying the database schema without running migrations
```
<!-- L3:END -->