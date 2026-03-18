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

**Trigger**: When working in backend/ directory and its main responsibility is to manage server-side logic and database interactions.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Run database migrations | `run_migrations_online()` |

## Critical Patterns (Summary)
- **Migration Management**: Use Alembic for handling database migrations.
- **Middleware Setup**: Implement custom middleware for request handling.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Migration Management

Use Alembic to manage database migrations effectively, ensuring the database schema is up-to-date.

```python
# apps/server/alembic/env.py
from alembic import context
from your_project import run_migrations_online

run_migrations_online()
```

### Middleware Setup

Implement custom middleware to handle cross-cutting concerns like logging and security.

```python
# apps/server/app/main.py
from fastapi import FastAPI
from .middleware import correlation_id_middleware

app = FastAPI()
app.middleware('http')(correlation_id_middleware)
```

## When to Use

- When adding new database models or modifying existing ones.
- When implementing new API endpoints that require middleware.

## Commands

```bash
# Run migrations
alembic upgrade head

# Start the FastAPI server
uvicorn apps.server.app.main:app --reload
```

## Anti-Patterns

### Don't: Modify database models without migration

Failing to run migrations after changing models can lead to inconsistencies in the database.

```python
# BAD
# Directly changing models without running migrations
```
<!-- L3:END -->