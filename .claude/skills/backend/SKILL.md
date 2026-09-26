---
name: backend-layer
description: >-
  Backend layer owns the FastAPI server, configuration, middleware, and
  Alembic migration scripts for the RepoForge application.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills: [frontend-layer, build_modules-layer]
load_priority: high
---

<!-- L1:START -->
# backend-layer

FastAPI server handling API, auth, logging, and DB migrations.

**Trigger**: When working in `backend/` directory — adding, modifying, or debugging server‑side routes, config, or middleware.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Add new route | `@app.get("/path")` |
| Configure middleware | `app.add_middleware(...)` |
| Run migrations | `run_async_migrations()` |

## Critical Patterns (Summary)
- **Route Declaration**: Use FastAPI decorators with explicit response models.
- **Middleware Registration**: