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

| Task               | Pattern                     |
|--------------------|-----------------------------|
| Add health check   | `health`                    |
| Add detailed health | `health_detailed`           |

## Critical Patterns (Summary)
- **health**: Implements a basic health check endpoint.
- **health_detailed**: Implements a detailed health check endpoint.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### health

Implements a basic health check endpoint that returns the status of the application.

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

### health_detailed

Implements a detailed health check endpoint that provides more information about the application status.

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

- When you need to expose a health check endpoint for monitoring.
- When you want to provide detailed application status for diagnostics.

## Commands

```bash
docker run -d -p 8000:8000 your-image-name
```

## Anti-Patterns

### Don't: Hardcode health responses

Hardcoding responses can lead to outdated information being served.

```python
# BAD
@app.get("/health")
async def health():
    return {"status": "not healthy"}  # This should be dynamic
```
<!-- L3:END -->