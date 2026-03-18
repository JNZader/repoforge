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

Implements a basic health check endpoint to verify the service is running.

```python
from fastapi import FastAPI
from apps.server.app.main import health

app = FastAPI()

@app.get("/health")
async def health_check():
    return health()
```

### health_detailed

Implements a detailed health check endpoint providing more information about the service status.

```python
from fastapi import FastAPI
from apps.server.app.main import health_detailed

app = FastAPI()

@app.get("/health/detailed")
async def detailed_health_check():
    return health_detailed()
```

## When to Use

- When you need to expose a health check endpoint for monitoring.
- When you want to provide detailed service status for diagnostics.

## Commands

```bash
docker-compose up
```

## Anti-Patterns

### Don't: Expose sensitive data in health checks

Exposing sensitive information can lead to security vulnerabilities.

```python
# BAD
@app.get("/health")
async def health_check():
    return {"status": "healthy", "db_password": "secret"}
```
<!-- L3:END -->