---
name: add-main-endpoint
description: >
  This skill covers adding main endpoints to the FastAPI application.
  Trigger: When setting up the main entry point for the application.
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

**Trigger**: When setting up the main entry point for the application.
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

Implements a global error handler to catch unhandled exceptions and return a standardized error response.

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": str(exc)})
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

Ignoring error handling can lead to unhandled exceptions crashing the application.

```python
# BAD
@app.get("/example")
async def example():
    raise Exception("This will crash the app")
```
<!-- L3:END -->