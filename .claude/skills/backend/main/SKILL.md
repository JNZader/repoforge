---
name: add-main-endpoint
description: >
  This skill covers adding main endpoints to the FastAPI application.
  Trigger: When setting up the main entry point for the application.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: medium
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
- **Health Check Endpoint**: Defines a simple health check for the application.
- **Global Error Handler**: Centralizes error handling for the FastAPI application.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Health Check Endpoint

Defines a simple health check for the application to ensure it's running.

```python
from fastapi import FastAPI
from apps.server.app.main import health

app = FastAPI()

@app.get("/health")
async def health_check():
    return health()
```

### Global Error Handler

Centralizes error handling for the FastAPI application to manage exceptions globally.

```python
from fastapi import FastAPI
from apps.server.app.main import global_error_handler

app = FastAPI()

@app.exception_handler(Exception)
async def custom_exception_handler(request, exc):
    return await global_error_handler(request, exc)
```

## When to Use

- When you need to implement a health check for your FastAPI application.
- When you want to handle errors globally across your application.

## Commands

```bash
docker-compose up
python apps/server/app/main.py
```

## Anti-Patterns

### Don't: Ignore Error Handling

Ignoring error handling can lead to unhandled exceptions and poor user experience.

```python
# BAD
@app.get("/example")
async def example():
    raise Exception("This will crash the app")
```
<!-- L3:END -->