---
name: add-schemas-model
description: >
  Provides concise patterns for defining and returning Pydantic v2 schemas in the RepoForge API.
  Trigger: when working with `schemas` in the backend.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 250
dependencies: []
related_skills:
  - extend-pydantic-model
  - handle-auth-responses
load_priority: high
---

<!-- L1:START -->
# add-schemas-model

Defines and returns Pydantic v2 request/response schemas for the RepoForge Web API.

**Trigger**: when working with `schemas` in the backend.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Create a request payload | `GenerateRequest(prompt=str, temperature=float)` |
| Return a detailed generation | `GenerationDetailWithEvents(id=UUID, events=list[GenerationEventDetail])` |
| Validate auth token | `AuthValidateResponse(valid=bool, user=UserInfo)` |

## Critical Patterns (Summary)
- **Define request schemas**: Use `GenerateRequest` with strict typing.
- **Structure response schemas**: Nest `GenerationDetail` inside `GenerationDetailWithEvents` for event tracking.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Define request schemas with `GenerateRequest`

Use the exported `GenerateRequest` to enforce input validation and automatic documentation.

```python
from apps.server.app.models.schemas import GenerateRequest

def parse_generate_body(body: dict) -> GenerateRequest:
    """Parse incoming JSON into a validated GenerateRequest."""
    return GenerateRequest(**body)
```

### Structure response schemas with `GenerationDetailWithEvents`

Combine `GenerationDetail` and `GenerationEventDetail` to return comprehensive generation data.

```python
from apps.server.app.models.schemas import (
    GenerationDetail,
    GenerationEventDetail,
    GenerationDetailWithEvents,
)

def build_generation_response(gen_id, detail, events):
    """Create a full response payload for a generation request."""
    return GenerationDetailWithEvents(
        id=gen_id,
        detail=GenerationDetail(**detail),
        events=[GenerationEventDetail(**e) for e in events],
    )
```

## When to Use

- When implementing a new endpoint that accepts generation parameters.
- When returning detailed generation results, including step‑by‑step events.
- When validating authentication responses with `AuthValidateResponse`.

## Commands

```bash
# Run the API locally with Docker
docker compose up --build

# Execute a CLI command that uses the schemas (e.g., generate)
python -m repoforge.cli generate --prompt "Explain quantum computing"
```

## Anti-Patterns

### Don't: expose raw ORM models directly in API responses

Returning database models bypasses validation and leaks internal fields.

```python
# BAD
from apps.server.db.models import Generation  # ORM model

def get_generation(gen_id):
    return Generation.query.get(gen_id)  # Returns ORM object directly
```
<!-- L3:END -->