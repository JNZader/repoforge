---
name: backend-layer
description: >
  This layer provides the backend functionality for the RepoForge application, 
  handling API requests, authentication, and database migrations.
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

This skill covers the backend functionality of the RepoForge application.

**Trigger**: When working in backend/ directory and its main responsibility is to manage API requests and services.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Configure logging | `configure_logging()` |
| Run migrations | `run_migrations_online()` |

## Critical Patterns (Summary)
- **Middleware Configuration**: Set up custom middleware for logging and authentication.
- **Database Migration**: Use Alembic for managing database schema changes.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Middleware Configuration

Set up custom middleware for logging and authentication to enhance request handling.

```python
# apps/server/app/main.py
app.add_middleware(correlation_id_middleware)
app.add_middleware(request_logging_middleware)
app.add_middleware(security_headers_middleware)
```

### Database Migration

Use Alembic for managing database schema changes, ensuring smooth transitions between versions.

```python
# apps/server/alembic/env.py
run_migrations_online()
```

## When to Use

- When implementing new API endpoints that require authentication.
- When modifying the database schema and needing to run migrations.

## Commands

```bash
# To run the server
docker-compose up

# To run migrations
python apps/server/alembic/env.py
```

## Anti-Patterns

### Don't: Change API response structures without versioning

This can break frontend integrations that rely on specific response formats.

```python
# BAD
return {"new_field": "value"}  # Unexpected change in response structure
```
<!-- L3:END -->