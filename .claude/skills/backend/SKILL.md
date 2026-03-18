---
name: backend-layer
description: >
  This layer owns the backend services for the RepoForge project, providing a FastAPI application and database management.
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
- **Middleware Usage**: Apply custom middleware for request handling.
- **Database Session Management**: Use async database sessions for operations.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Middleware Usage

Apply custom middleware for request handling to enhance security and logging.

```python
# Example using real exported names
from apps.server.app.main import correlation_id_middleware
```

### Database Session Management

Use async database sessions for operations to ensure non-blocking I/O.

```python
# Example using real exported names
from apps.server.app.models.database import get_db
```

## When to Use

- When implementing authentication and authorization features.
- When setting up database interactions for models.

## Commands

```bash
uvicorn apps.server.app.main:app --reload
```

## Anti-Patterns

### Don't: Modify database models without migration

This can lead to inconsistencies and application crashes.

```python
# BAD
# Directly changing models without running migrations
```
<!-- L3:END -->