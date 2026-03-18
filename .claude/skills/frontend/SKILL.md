---
name: frontend-layer
description: >
  This layer manages the user interface and user experience of the application.
  Trigger: When working in frontend/ — adding, modifying, or debugging UI components.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: medium
  token_estimate: 450
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# frontend-layer

This layer manages the user interface and user experience of the application.

**Trigger**: When working in frontend/ — adding, modifying, or debugging UI components.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task               | Pattern                          |
|--------------------|----------------------------------|
| Create a new component | `export const NewComponent = () => { ... }` |

## Critical Patterns (Summary)
- **Component Structure**: Each component should be a functional component.
- **Error Handling**: Use ErrorBoundary for catching errors in the UI.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Component Structure

Each component should be a functional component that returns JSX.

```typescript
// Example of a functional component
export const NewComponent = () => {
  return <div>Hello World</div>;
};
```

### Error Handling

Use ErrorBoundary to catch errors in the UI and display a fallback UI.

```typescript
// Example of using ErrorBoundary
<ErrorBoundary>
  <Layout />
</ErrorBoundary>
```

## When to Use

- When creating reusable UI components.
- When implementing error boundaries for better user experience.

## Commands

```bash
npm run start
npm run build
```

## Anti-Patterns

### Don't: Modify shared components without coordination

Changing shared components can lead to inconsistencies across the application.

```typescript
// BAD: Directly modifying a shared component
const Layout = () => {
  return <div>Modified Layout</div>; // This can break other parts of the app
};
```
<!-- L3:END -->