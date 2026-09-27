---
name: configure-main-middleware
description: >
  Sets up core FastAPI middleware and health endpoints for the RepoForge server.
  Trigger: when the `main` FastAPI app is initialized.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills:
  - add-health-endpoint
  - setup-fastapi-lifespan
load_priority: high
---

<!-- L1:START -->
# configure-main-middleware

Configures essential middleware and health routes for the FastAPI `main` application.

**Trigger**: loading the `main` module at server start‑up.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task                         | Pattern |
|------------------------------|---------|
| Add correlation ID middleware| `correlation_id_middleware` |
| Log each request             | `request_logging_middleware` |
| Expose health checks         | `health`, `health_detailed` |

## Critical Patterns (Summary)
- **Add Correlation ID Middleware**: injects a unique request ID into logs and response headers.
- **Expose Health Endpoints**: provides `/health` and `/health/detailed` for liveness and diagnostics.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Add Correlation ID Middleware

Ensures every incoming request carries a UUID that is logged and returned in the `X-Request-ID` header, aiding traceability across services.

```python
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```

### Expose Health Endpoints

Provides lightweight JSON health checks; `health` returns basic status, while `health_detailed` includes version and uptime.

```python
@app.get("/health")
async def health() -> dict:
    return await health()

@app.get("/health/detailed")
async def health_detailed() -> dict:
    return await health_detailed()
```

## When to Use

- When initializing the FastAPI `main` app and you need request tracing.
- When you want observable liveness endpoints for Kubernetes or CI checks.
- When debugging startup failures and need detailed runtime diagnostics.

## Commands

```bash
# Build the Docker image
docker build -t repoforge-server:0.3.0 .

# Run the server locally
uvicorn apps.server.app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Anti-Patterns

### Don't: Register the same middleware multiple times

Duplicating middleware leads to duplicated headers, double logging, and performance overhead.

```python
# BAD – middleware applied twice
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    ...

@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    ...
```
<!-- L3:END -->