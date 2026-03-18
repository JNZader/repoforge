---
name: backend-layer
description: >
  This layer owns the backend services for the RepoForge project, providing a FastAPI application and middleware for authentication, logging, and rate limiting.
  Trigger: When working in backend/ — adding, modifying, or debugging backend services.
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

This skill covers the backend services for the RepoForge project.

**Trigger**: When working in backend/ directory and its main responsibility is to manage backend services.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Configure logging | `configure_logging()` |
| Run migrations | `run_migrations_online()` |

## Critical Patterns (Summary)
- **Middleware Configuration**: Set up custom middleware for logging, authentication, and rate limiting.
- **Migration Management**: Use Alembic for managing database migrations effectively.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Middleware Configuration

Set up custom middleware for logging, authentication, and rate limiting to enhance the FastAPI application.

```python
# apps/server/app/main.py
app.add_middleware(correlation_id_middleware)
app.add_middleware(request_logging_middleware)
app.add_middleware(security_headers_middleware)
```

### Migration Management

Use Alembic to manage database migrations effectively, ensuring the database schema is up to date.

```python
# apps/server/alembic/env.py
run_migrations_online()
```

## When to Use

- When implementing new features that require backend services.
- When debugging issues related to API endpoints or middleware.

## Commands

```bash
# Run the FastAPI application
uvicorn apps.server.app.main:app --reload

# Run database migrations
alembic upgrade head
```

## Anti-Patterns

### Don't: Change middleware without testing

Changing middleware can break the authentication or logging flow, leading to security vulnerabilities or loss of important logs.

```python
# BAD
app.add_middleware(SomeNewMiddleware)
```
<!-- L3:END -->