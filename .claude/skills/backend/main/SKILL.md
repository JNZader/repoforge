---
name: add-main-endpoint
description: >
  This skill covers adding main endpoints to the FastAPI application.
  Trigger: When setting up the main entry point for the FastAPI application.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: low
  token_estimate: 350
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# add-main-endpoint

This skill covers adding main endpoints to the FastAPI application.

**Trigger**: When setting up the main entry point for the FastAPI application.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Add health check endpoint | `health` |
| Implement global error handling | `global_error_handler` |

## Critical Patterns (Summary)
- **health**: Defines a health check endpoint for the application.
- **global_error_handler**: Implements a global error handler for unhandled exceptions.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### health

Defines a health check endpoint for the application, allowing clients to verify the service's status.

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

### global_error_handler

Implements a global error handler for unhandled exceptions, ensuring consistent error responses.

```python
from fastapi import FastAPI
from starlette.middleware.errors import ServerErrorMiddleware

app = FastAPI()

@app.exception_handler(Exception)
async def global_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"message": "Internal Server Error"})
```

## When to Use

- When creating a health check endpoint for monitoring.
- When implementing error handling across the FastAPI application.

## Commands

```bash
uvicorn apps.server.app.main:app --reload
```

## Anti-Patterns

### Don't: Ignore error handling

Ignoring error handling can lead to uninformative responses and application crashes.

```python
# BAD
@app.get("/example")
async def example():
    raise Exception("This will crash the app")
```
<!-- L3:END -->