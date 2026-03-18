---
name: usegenerationstream-hook
description: >
  This skill covers the use of the `useGenerationStream` hook for managing streaming states.
  Trigger: Load when implementing streaming functionality in the frontend.
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

This skill covers the use of the `useGenerationStream` hook for managing streaming states.

**Trigger**: Load when implementing streaming functionality in the frontend.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Manage stream status | `useGenerationStream` |
| Define step items | `StepItem` |

## Critical Patterns (Summary)
- **Manage stream status**: Utilize `useGenerationStream` to handle the streaming state.
- **Define step items**: Create and manage `StepItem` instances for each step in the stream.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Manage stream status

Use the `useGenerationStream` hook to manage the streaming state effectively.

```typescript
import { useGenerationStream, StreamStatus } from '@/hooks/useGenerationStream';

const MyComponent = () => {
  const { status } = useGenerationStream();

  if (status === StreamStatus.Loading) {
    return <LoadingSpinner />;
  }

  return <div>Stream is ready!</div>;
};
```

### Define step items

Create and manage `StepItem` instances to represent each step in the streaming process.

```typescript
import { StepItem } from '@/hooks/useGenerationStream';

const steps: StepItem[] = [
  { id: 1, name: 'Step 1', completed: false },
  { id: 2, name: 'Step 2', completed: true },
];
```

## When to Use

- When implementing a streaming feature in a React component.
- When tracking the progress of a multi-step process.

## Commands

```bash
docker-compose up
python repoforge/cli.py
```

## Anti-Patterns

### Don't: Ignore stream status

Ignoring the stream status can lead to unresponsive UI and poor user experience.

```typescript
// BAD
const MyComponent = () => {
  const { status } = useGenerationStream();
  return <div>Stream is running...</div>; // No status handling
};
```
<!-- L3:END -->