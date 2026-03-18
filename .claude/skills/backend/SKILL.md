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
| Create a new database model | `apps/server/app/models/__init__.py` |
| Configure application settings | `apps/server/app/config.py` |

## Critical Patterns (Summary)
- **Database Model Definition**: Define ORM models in `models/__init__.py`.
- **Middleware Setup**: Implement custom middleware in `middleware/__init__.py`.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Database Model Definition

Define ORM models in `models/__init__.py` to represent database tables and relationships.

```python
# apps/server/app/models/__init__.py
from sqlalchemy import Column, Integer, String
from .database import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
```

### Middleware Setup

Implement custom middleware in `middleware/__init__.py` to handle requests and responses.

```python
# apps/server/app/middleware/__init__.py
from starlette.middleware.base import BaseHTTPMiddleware

class CustomMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        return response
```

## When to Use

- When creating new database models for the application.
- When implementing custom middleware for request handling.

## Commands

```bash
# Run migrations
python -m alembic upgrade head

# Start the FastAPI server
uvicorn apps.server.app.main:app --reload
```

## Anti-Patterns

### Don't: Modify database models without migrations

Changing database models directly can lead to inconsistencies and data loss.

```python
# BAD
# Directly altering the User model without running migrations
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String)  # Adding a new field without migration
```
<!-- L3:END -->