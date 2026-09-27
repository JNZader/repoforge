---
name: add-main-endpoints
description: >
  FastAPI application setup with middlewares, health checks, and lifespan management.
  Trigger: when initializing the main FastAPI application or adding health endpoints.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: medium
  token_estimate: 650
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# add-main-endpoints

FastAPI application setup with middlewares, health checks, and lifespan management.

**Trigger**: when initializing the main FastAPI application or adding health endpoints.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Setup middlewares | `correlation_id_middleware` |
| Health check | `GET /health` |
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Pattern 1: Application Lifespan & Middleware Setup

Configure FastAPI lifespan and register all HTTP middlewares (correlation ID, request logging, security headers) at application startup.

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager

from apps.server.app.main import lifespan, correlation_id_middleware, request_logging_middleware, security_headers_middleware

app = FastAPI(lifespan=lifespan)

app.middleware("http")(correlation_id_middleware)
app.middleware("http")(request_logging_middleware)
app.middleware("http")(security_headers_middleware)
```

### Pattern 2: Health Check Endpoints

Define two health check endpoints: a basic `GET /health` returning status and a detailed `GET /health/detailed` with system information.

```python
@app.get("/health")
async def health() -> dict:
    """Basic health check endpoint."""
    return {"status": "ok"}

@app.get("/health/detailed")
async def health_detailed() -> dict:
    """Detailed health check endpoint."""
    return {"status": "ok", "version": "0.3.0"}
```

## When to Use

- Initializing the RepoForge Web backend FastAPI application
- Adding or modifying middleware pipeline for request processing
- Exposing health check endpoints for monitoring and load balancer checks

## Commands

```bash
# Start the server with uvicorn
uvicorn apps.server.app.main:app --reload

# Run database migrations
alembic upgrade head
```

## Anti-Patterns

### Don't: Forget to register middlewares

Omitting `app.middleware("http")(...)` calls means middlewares defined in `lifespan` or elsewhere will not execute, breaking request ID tracking, logging, and security headers.

```python
# BAD: Missing middleware registration
app = FastAPI(lifespan=lifespan)  # middlewares not attached
```
<!-- L3:END -->