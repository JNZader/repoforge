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
- **Health Check Endpoint**: Define a health check endpoint for application status.
- **Global Error Handling**: Set up a global error handler for consistent error responses.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Health Check Endpoint

Define a health check endpoint for application status.

```python
from fastapi import FastAPI
from apps.server.app.main import health

app = FastAPI()

@app.get("/health")
async def health_check():
    return health()
```

### Global Error Handling

Set up a global error handler for consistent error responses.

```python
from fastapi import FastAPI
from apps.server.app.main import global_error_handler

app = FastAPI()

@app.exception_handler(Exception)
async def custom_exception_handler(request, exc):
    return await global_error_handler(request, exc)
```

## When to Use

- When you need to expose a health check for monitoring.
- When implementing a consistent error handling strategy across the application.

## Commands

```bash
uvicorn apps.server.app.main:app --reload
```

## Anti-Patterns

### Don't: Ignore Error Handling

Ignoring error handling can lead to uninformative responses and poor user experience.

```python
# BAD
@app.get("/example")
async def example():
    raise Exception("An error occurred")
```
<!-- L3:END -->