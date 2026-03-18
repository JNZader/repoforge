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
| Configure logging | `configure_logging()` |
| Run migrations | `run_migrations_online()` |

## Critical Patterns (Summary)
- **Middleware Configuration**: Set up custom middleware for request handling.
- **Database Migration**: Manage database schema changes using Alembic.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Middleware Configuration

Set up custom middleware for handling requests, such as logging and authentication.

```python
# apps/server/app/main.py
app.add_middleware(correlation_id_middleware)
app.add_middleware(request_logging_middleware)
app.add_middleware(security_headers_middleware)
```

### Database Migration

Manage database schema changes using Alembic for version control.

```python
# apps/server/alembic/env.py
run_migrations_online()
```

## When to Use

- When implementing new API endpoints that require authentication.
- When modifying database schemas and needing to run migrations.

## Commands

```bash
# To run the server
uvicorn apps.server.app.main:app --reload

# To run migrations
alembic upgrade head
```

## Anti-Patterns

### Don't: Change API response formats without updating the frontend

This can lead to broken integrations and user-facing errors.

```python
# BAD
return {"message": "success"}  # Frontend expects a different structure
```
<!-- L3:END -->