---
name: configure-main-app
description: >
  Sets up core FastAPI entry point patterns for RepoForge Web.
  Trigger: main
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 250
dependencies: []
related_skills:
  - add-health-endpoint
  - setup-middleware
load_priority: high
---

<!-- L1:START -->
# configure-main-app

Configure the FastAPI `main` application with health routes, middleware, and error handling.

**Trigger**: main
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Add health endpoint | `@app.get("/health")(health)` |
| Register correlation ID middleware | `app.middleware("http")(correlation_id_middleware)` |
| Global error handling | `app.exception_handler(Exception)(global_error_handler)` |

## Critical Patterns (Summary)
- **Lifespan Hook**: Use `lifespan` to manage startup/shutdown resources.
- **HTTP Middleware Stack**: Attach `correlation_id_middleware`, `request_logging_middleware`, and `security_headers_middleware` in order.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Lifespan Hook

Define an async generator to run initialization (e.g., DB connections) and cleanup when the app starts and stops.

```python
from fastapi import FastAPI
from typing import AsyncGenerator

async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # startup logic
    await app.state.db.connect()
    yield
    # shutdown logic
    await app.state.db.disconnect()
```

Register it when creating the FastAPI instance:

```python
app = FastAPI(lifespan=lifespan)
```

### HTTP Middleware Stack

Add request‑wide middleware for correlation IDs, logging, and security headers using the exported functions.

```python
from fastapi import FastAPI, Request

app = FastAPI()

app.middleware("http")(correlation_id_middleware)
app.middleware("http")(request_logging_middleware)
app.middleware("http")(security_headers_middleware)
```

Each middleware follows the signature:

```python
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    # implementation …
    response = await call_next(request)
    return response
```

## When to Use

- When initializing the server and need deterministic startup/shutdown steps.
- To ensure every request carries a correlation ID, is logged, and receives security headers.
- To provide consistent JSON error responses via `global_error_handler`.

## Commands

```bash
# Build the Docker image
docker build -t repoforge/server:0.3.0 .

# Run the container
docker run -p 8000:8000 repoforge/server:0.3.0

# Start locally with Uvicorn
uvicorn apps.server.app.main:app --host 0.0.0.0 --port 8000
```

## Anti-Patterns

### Don't: Omit `call_next` in middleware

Skipping `call_next` prevents the request from reaching downstream handlers, causing 404s or hanging connections.

```python
@app.middleware("http")
async def bad_middleware(request: Request, call_next):
    # BAD: never calls the next handler
    return JSONResponse({"error": "middleware blocked"})
```
<!-- L3:END -->