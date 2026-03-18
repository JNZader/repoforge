---
name: frontend-layer
description: >
  This layer manages the user interface and user experience of the application.
  Trigger: When working in frontend/ — adding, modifying, or debugging UI components and interactions.
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

**Trigger**: When working in frontend/ — adding, modifying, or debugging UI components and interactions.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task               | Pattern                          |
|--------------------|----------------------------------|
| Create a new component | `export const NewComponent = () => { ... }` |

## Critical Patterns (Summary)
- **Component Structure**: Each component should be a functional component returning JSX.
- **Error Handling**: Use ErrorBoundary to catch and display errors gracefully.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Component Structure

Each component should be a functional component returning JSX.

```typescript
// Example using real exported names
export const Layout = () => {
  return <div className="layout">...</div>;
};
```

### Error Handling

Use ErrorBoundary to catch and display errors gracefully.

```typescript
// Example
<ErrorBoundary>
  <App />
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

Changing shared components can break the UI for other layers relying on them.

```typescript
// BAD
const Layout = () => {
  return <div className="layout modified">...</div>; // This can affect other parts of the app
};
```
<!-- L3:END -->