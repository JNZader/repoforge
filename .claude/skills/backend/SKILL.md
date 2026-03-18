---
name: backend-layer
description: >
  This layer provides the FastAPI backend for the RepoForge Web application, handling API requests, authentication, and middleware.
  Trigger: When working in backend/ — adding, modifying, or debugging server-side logic.
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

This skill covers the backend functionality of the RepoForge Web application.

**Trigger**: When working in backend/ directory and its main responsibility is to manage server-side logic.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Configure logging | `configure_logging()` |
| Run migrations | `run_migrations_online()` |

## Critical Patterns (Summary)
- **Middleware Configuration**: Set up custom middleware for request handling.
- **Database Migration**: Manage database schema changes using Alembic.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Middleware Configuration

Set up custom middleware for handling requests and responses in FastAPI.

```python
# apps/server/app/main.py
from .middleware.logging_config import configure_logging

app = FastAPI()
configure_logging()
```

### Database Migration

Manage database schema changes using Alembic for version control.

```python
# apps/server/alembic/env.py
from alembic import context
from . import run_migrations_online

run_migrations_online()
```

## When to Use

- When implementing new API endpoints that require authentication.
- When modifying existing database schemas and ensuring migrations are applied.

## Commands

```bash
# Run the FastAPI server
uvicorn apps.server.app.main:app --reload

# Apply database migrations
alembic upgrade head
```

## Anti-Patterns

### Don't: Change API response formats without versioning

This can break frontend integrations that rely on specific response structures.

```python
# BAD
@app.get("/items")
def get_items():
    return {"items": ["item1", "item2"]}  # Changing response structure without versioning
```
<!-- L3:END -->