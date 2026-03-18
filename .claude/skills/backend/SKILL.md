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
- **Middleware Configuration**: Set up custom middleware for logging, authentication, and rate limiting.
- **Migration Management**: Handle database migrations using Alembic for schema changes.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Middleware Configuration

Set up custom middleware for logging, authentication, and rate limiting to enhance request handling.

```python
# apps/server/app/main.py
app.add_middleware(correlation_id_middleware)
app.add_middleware(request_logging_middleware)
app.add_middleware(security_headers_middleware)
```

### Migration Management

Handle database migrations using Alembic for schema changes, ensuring the database is up-to-date with the application code.

```python
# apps/server/alembic/env.py
run_migrations_online()
```

## When to Use

- When implementing new API endpoints that require authentication.
- When modifying existing database schemas and needing to run migrations.

## Commands

```bash
# To run the FastAPI server
uvicorn apps.server.app.main:app --reload

# To run migrations
alembic upgrade head
```

## Anti-Patterns

### Don't: Modify middleware without testing

Changing middleware can break existing functionality and lead to security vulnerabilities.

```python
# BAD
app.add_middleware(new_middleware)  # Without testing
```
<!-- L3:END -->