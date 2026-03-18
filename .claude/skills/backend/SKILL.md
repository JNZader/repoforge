---
name: backend-layer
description: >
  This layer provides the backend functionality for the RepoForge application, 
  handling API requests, authentication, and database migrations.
  Trigger: When working in backend/ — adding, modifying, or debugging server-side logic.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: medium
  token_estimate: 800
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# backend-layer

This skill covers the backend functionality of the RepoForge application.

**Trigger**: When working in backend/ directory and its main responsibility is to manage server-side logic.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Configure logging | `from apps.server.app.middleware.logging_config import configure_logging` |

## Critical Patterns (Summary)
- **Middleware Configuration**: Use custom middleware for request handling and logging.
- **Database Migration**: Manage database schema changes using Alembic.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Middleware Configuration

Custom middleware can be added to handle various aspects of request processing, such as authentication and logging.

```python
# Example of adding a middleware
from apps.server.app.middleware.auth import get_current_user
```

### Database Migration

Alembic is used for managing database migrations, allowing for version control of the database schema.

```python
# Example of running migrations
from apps.server.alembic.env import run_migrations_online
```

## When to Use

- When implementing new API endpoints that require authentication.
- When modifying the database schema and needing to apply migrations.

## Commands

```bash
# Run the FastAPI server
uvicorn apps.server.app.main:app --reload

# Run migrations
python apps/server/alembic/env.py
```

## Anti-Patterns

### Don't: Change API response formats without updating the frontend

This can lead to mismatches between the backend and frontend, causing errors in data handling.

```python
# BAD
return {"message": "success"}  # If frontend expects a different structure
```
<!-- L3:END -->