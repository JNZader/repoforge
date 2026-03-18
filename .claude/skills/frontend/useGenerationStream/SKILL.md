---
name: usegenerationstream-hook
description: >
  This skill covers patterns for using the `useGenerationStream` hook.
  Trigger: Load when managing streaming generation states in the frontend.
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

**Trigger**: Load when managing streaming generation states in the frontend.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Get stream status | `StreamStatus` |
| Handle step items | `StepItem` |

## Critical Patterns (Summary)
- **StreamStatus**: Use to manage and display the current status of the generation stream.
- **StepItem**: Utilize to represent individual steps in the generation process.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### StreamStatus

Use `StreamStatus` to manage and display the current status of the generation stream.

```typescript
import { StreamStatus } from '@/hooks/useGenerationStream';

const status: StreamStatus = { isLoading: true, error: null };
```

### StepItem

Utilize `StepItem` to represent individual steps in the generation process.

```typescript
import { StepItem } from '@/hooks/useGenerationStream';

const step: StepItem = { id: 1, description: 'Generating data...' };
```

## When to Use

- When you need to track the status of a generation process in your UI.
- When displaying individual steps of a generation task to the user.

## Commands

```bash
docker-compose up
python repoforge/cli.py
```

## Anti-Patterns

### Don't: Ignore stream state management

Ignoring the management of stream states can lead to unresponsive UI and poor user experience.

```typescript
// BAD
const status = { isLoading: false, error: null }; // No state management
```
<!-- L3:END -->