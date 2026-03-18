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
| Add detailed health check endpoint | `health_detailed` |

## Critical Patterns (Summary)
- **health**: Implements a basic health check endpoint.
- **health_detailed**: Implements a detailed health check endpoint.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### health

Implements a basic health check endpoint to verify the service is running.

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

### health_detailed

Implements a detailed health check endpoint providing more information about the service status.

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/health/detailed")
async def health_detailed():
    return {
        "status": "healthy",
        "details": {
            "database": "connected",
            "cache": "operational"
        }
    }
```

## When to Use

- When creating a new FastAPI application.
- When adding health check functionality to an existing service.

## Commands

```bash
docker run -d -p 8000:8000 my-fastapi-app
```

## Anti-Patterns

### Don't: Hardcode health check responses

Hardcoding responses can lead to outdated information being served.

```python
# BAD
@app.get("/health")
async def health():
    return {"status": "not healthy"}  # This may not reflect the actual state
```
<!-- L3:END -->