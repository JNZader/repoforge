---
name: configure-main-app
description: >
  Sets up core FastAPI entry point with health routes and essential middleware.
  Trigger: loading the main FastAPI application.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills:
  - add-health-endpoint
  - setup-middleware
load_priority: high
---

<!-- L1:START -->
# configure-main-app

Configures the FastAPI `main` app with health checks and middleware stack.

**Trigger**: When the `main` module is imported to start the server.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task                     | Pattern |
|--------------------------|---------|
| expose health routes    | `health`, `health_detailed` |
| add request middleware  | `correlation_id_middleware`, `request_logging_middleware`, `security_headers_middleware` |

## Critical Patterns (Summary)
- **Add health endpoints**: Register `/health` and `/health/detailed` using `health` and `health_detailed`.
- **Integrate request middleware**: Attach correlation, logging, and security headers middleware before the app runs.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Add health endpoints

Expose lightweight and detailed health checks for monitoring. Register the routes on the FastAPI instance before the app starts.

```python
from fastapi import FastAPI
from apps.server.app.main import health, health_detailed

app = FastAPI(lifespan=lifespan)

app.add_api_route("/health", health, methods=["GET"])
app.add_api_route("/health/detailed", health_detailed, methods=["GET"])
```

### Integrate request middleware

Apply correlation IDs, structured request logging, and security headers early in the request lifecycle to ensure consistent tracing and protection.

```python
from apps.server.app.main import (
    correlation_id_middleware,
    request_logging_middleware,
    security_headers_middleware,
)

app.add_middleware(correlation_id_middleware)
app.add_middleware(request_logging_middleware)
app.add_middleware(security_headers_middleware)
```

## When to Use

- Initializing the server for the first time or during CI/CD container builds.
- Adding or updating health monitoring in production deployments.
- Refactoring request tracing or security policies.

## Commands

```bash
docker build -t repoforge-server .
docker run --rm -p 8000:8000 repoforge-server
uvicorn apps.server.app.main:app --reload
```

## Anti-Patterns

### Don't: Register middleware after the app has started

Adding middleware after the FastAPI instance is running bypasses the request lifecycle and leaves requests untracked.

```python
# BAD
app = FastAPI()
# ... later in code
app.add_middleware(request_logging_middleware)  # too late
```
<!-- L3:END -->