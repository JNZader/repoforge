---
name: start-generation
description: >
  This skill covers the generation routes for starting, streaming, canceling, downloading, and previewing.
  Trigger: When generating content.
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
# start-generation

This skill covers the generation routes for starting, streaming, canceling, downloading, and previewing.

**Trigger**: When generating content.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Start generation | `start_generation()` |
| Stream generation | `stream_generation()` |

## Critical Patterns (Summary)
- **Start Generation**: Initiates the generation process.
- **Stream Generation**: Streams the ongoing generation process.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Start Generation

Initiates the generation process and returns a response indicating the status.

```python
from apps.server.app.routes.generate import start_generation

response = start_generation(data)
```

### Stream Generation

Streams the ongoing generation process, allowing real-time updates.

```python
from apps.server.app.routes.generate import stream_generation

for update in stream_generation(job_id):
    print(update)
```

## When to Use

- When a user requests to start a new generation task.
- When streaming updates for an ongoing generation process.

## Commands

```bash
docker-compose up
python repoforge/cli.py start
```

## Anti-Patterns

### Don't: Block the main thread

Blocking the main thread during generation can lead to unresponsive applications.

```python
# BAD
result = start_generation(data)
while not result.is_complete():
    pass  # This blocks the main thread
```
<!-- L3:END -->