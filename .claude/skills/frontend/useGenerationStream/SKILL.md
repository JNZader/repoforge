---
name: usegenerationstream-hook
description: >
  This skill covers patterns for managing generation streams in a React application.
  Trigger: Load when using `useGenerationStream` for state management.
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

This skill covers patterns for managing generation streams in a React application.

**Trigger**: Load when using `useGenerationStream` for state management.
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
import { StreamStatus, useGenerationStream } from '@/hooks/useGenerationStream';

const MyComponent = () => {
  const { status } = useGenerationStream();

  if (status === StreamStatus.Loading) {
    return <LoadingSpinner />;
  }
  return <div>Stream is ready!</div>;
};
```

### Handle step items

Use `StepItem` to represent individual steps in the generation process, enabling detailed tracking of progress.

```typescript
import { StepItem, useGenerationStream } from '@/hooks/useGenerationStream';

const MyComponent = () => {
  const { steps } = useGenerationStream();

  return (
    <ul>
      {steps.map((step: StepItem) => (
        <li key={step.id}>{step.description}</li>
      ))}
    </ul>
  );
};
```

## When to Use

- When managing the state of a generation process in a React component.
- When displaying progress through individual steps of a generation task.

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
  const { data } = useGenerationStream();
  return <div>{data}</div>; // No status handling
};
```
<!-- L3:END -->