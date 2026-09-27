---
name: backend-layer
description: >
  Python FastAPI backend layer for RepoForge Web. Handles HTTP requests, authentication, migrations, and health checks.
  Trigger: When working in backend/ directory — adding routes, modifying middleware, or debugging server behavior.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: medium
token_estimate: 1200
dependencies: []
related_skills: [frontend-layer, build_modules-layer]
load_priority: high
---


<!-- L1:START -->
# backend-layer

The Python FastAPI backend layer for RepoForge Web, handling HTTP requests, authentication, migrations, and health checks.

**Trigger**: When working in `backend/` directory — adding routes, modifying middleware, or debugging server behavior.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Run migrations | `alembic upgrade head` |
| Start server | `uvicorn app.main:app --reload` |
| Test endpoints | `pytest tests/` |

## Critical Patterns (Summary)
- **FastAPI Middleware**: All request processing goes through correlation_id, logging, and security_headers middleware in defined order.
- **Migration Runner**: Alembic env.py provides async offline/online migration functions for schema changes.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Pattern 1: FastAPI Middleware Pipeline

Request flows through correlation_id → logging → security_headers → route handler. Each middleware is a FastAPI `@app.middleware("http")` dependency that adds headers or context before passing to the next layer.

```python
# apps/server/app/main.py
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    request.state.correlation_id = str(uuid4())
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = request.state.correlation_id
    return response
```

### Pattern 2: Alembic Migration Runner

Offline migrations run without DB connection; online migrations establish async connection via `run_async_migrations()` to perform schema changes.

```python
# apps/server/alembic/env.py
def run_migrations_offline() -> None:
    context = context.configure(url=url, literal_binds=True)
    with context.begin():
        do_run_migrations(context)

async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.CONFIG_SECTION), prefix="sqlalchemy."
    )
    async with connectable.begin() as connection:
        await connection.run_sync(do_run_migrations, thread=True)
```
## When to Use

- Adding new API routes — use `GET /health` and `GET /health/detailed` patterns as reference
- Modifying request logging — adjust `configure_logging()` in `apps/server/app/middleware/logging_config.py`
- Implementing authentication — add JWT dependency via `get_current_user` in `apps/server/app/middleware/auth.py`

## Adding a New Route

1. Define route in `apps/server/app/routes/` — follow existing `providers.py` or `auth.py` pattern
2. Add middleware if auth/logging needed — inject `get_current_user` or `configure_logging()`
3. Register in FastAPI app lifespan if startup logic required
4. Verify: `pytest tests/ -k "<route_name>"`

## Commands

```bash
uvicorn app.main:app --reload
alembic upgrade head
pytest tests/ -k "health"
```

## Anti-Patterns

### Don't: Skip middleware pipeline order

Placing security headers after route handlers or omitting correlation_id breaks request tracing and security. Middleware must wrap the full request lifecycle.

```python
# BAD - security headers too late
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)  # headers set after handler
    response.headers["X-SECURITY"] = "true"
    return response
```
<!-- L3:END -->