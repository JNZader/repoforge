---
name: usegenerationstream-hook
description: >
  This skill covers patterns for using the `useGenerationStream` hook.
  Trigger: When implementing streaming generation in the frontend.
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
# usegenerationstream-hook

This skill covers patterns for using the `useGenerationStream` hook.

**Trigger**: When implementing streaming generation in the frontend.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Manage stream status | `StreamStatus` |
| Handle step items | `StepItem` |

## Critical Patterns (Summary)
- **Manage stream status**: Utilize `StreamStatus` to track the state of the generation stream.
- **Handle step items**: Use `StepItem` to represent individual steps in the generation process.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Manage stream status

Utilize `StreamStatus` to track the state of the generation stream, allowing for responsive UI updates.

```typescript
import { StreamStatus } from '@/hooks/useGenerationStream';

const status: StreamStatus = StreamStatus.STARTING;
```

### Handle step items

Use `StepItem` to represent individual steps in the generation process, enabling detailed tracking of progress.

```typescript
import { StepItem } from '@/hooks/useGenerationStream';

const step: StepItem = { id: 1, description: 'Generating data...' };
```

## When to Use

- When implementing a user interface that requires real-time updates from a generation process.
- When managing multiple steps in a generation workflow.

## Commands

```bash
docker-compose up
python repoforge/cli.py
```

## Anti-Patterns

### Don't: Ignore stream state management

Ignoring the management of stream states can lead to unresponsive UIs and poor user experience.

```typescript
// BAD
const status = StreamStatus.RUNNING; // No state management
```
<!-- L3:END -->