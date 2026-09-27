---
name: backend-layer
description: >
  The backend layer (apps/server) owns the FastAPI server, async Alembic migrations,
  and all middleware/configuration for the RepoForge web service.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills:
  - frontend-layer
  - build_modules-layer
load_priority: high
---

<!-- L1:START -->
# backend-layer

Provides the FastAPI API, database migrations, and request‑handling middleware for the RepoForge server.

**Trigger**: When working in `backend/` directory — adding, modifying, or debugging server‑side routes, migrations, or middleware.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | File | Pattern |
|------|------|---------|
| Run async migrations | `apps/server/alembic/env.py` | `run_async_migrations()` |
| Retrieve current user | `apps/server/app/middleware/auth.py` | `get_current_user(request)` |
| Initialise structured logging | `apps/server/app/middleware/logging_config.py` | `configure_logging()` |

## Critical Patterns (Summary)
- **FastAPI Middleware Pattern**: Register HTTP middlewares with `@app.middleware("http")` and keep them stateless.
- **Alembic Async Migration Pattern**: Use `run_async_migrations()` for non‑blocking DB schema upgrades.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### FastAPI Middleware Pattern

All request‑level concerns (correlation IDs, logging, security headers) are implemented as async middlewares
decorated with `@app.middleware("http")`. Keep each middleware pure and order‑independent.

```python
# apps/server/app/main.py
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = request.state.correlation_id
    return response

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    logger.info("Incoming request", path=request.url.path)
    return await call_next(request)

@app.middleware("http")
async def security_headers_m