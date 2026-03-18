---
name: usegenerationstream-hook
description: >
  This skill covers patterns for using the `useGenerationStream` hook.
  Trigger: Load when managing streaming generation states in the frontend.
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
# usegenerationstream-hook

This skill covers patterns for using the `useGenerationStream` hook.

**Trigger**: Load when managing streaming generation states in the frontend.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Get stream status | `StreamStatus` |
| Handle step items | `StepItem` |

## Critical Patterns (Summary)
- **Get Stream Status**: Retrieve the current status of the generation stream.
- **Handle Step Items**: Manage individual steps in the generation process.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Get Stream Status

Retrieve the current status of the generation stream using `StreamStatus`.

```typescript
import { StreamStatus, useGenerationStream } from '@/hooks/useGenerationStream';

const { status } = useGenerationStream();
console.log(status); // Outputs the current stream status
```

### Handle Step Items

Manage individual steps in the generation process with `StepItem`.

```typescript
import { StepItem, useGenerationStream } from '@/hooks/useGenerationStream';

const { steps } = useGenerationStream();
steps.forEach((step: StepItem) => {
  console.log(step); // Outputs each step item
});
```

## When to Use

- When you need to track the status of a generation process in your UI.
- When handling multiple steps in a streaming generation task.

## Commands

```bash
docker-compose up
python repoforge/cli.py
```

## Anti-Patterns

### Don't: Ignore Stream State

Ignoring the stream state can lead to unhandled errors and poor user experience.

```typescript
// BAD
const { status } = useGenerationStream();
// Not checking status before proceeding
```
<!-- L3:END -->