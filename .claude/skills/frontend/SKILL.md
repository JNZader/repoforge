---
name: frontend-layer
description: >
  This layer manages the user interface and client-side logic of the application.
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

This skill covers the frontend layer of the application, focusing on UI components and client-side logic.

**Trigger**: When working in frontend/ directory and its main responsibility is to manage user interactions and display data.
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

Each component should be a functional component returning JSX, ensuring a consistent structure across the application.

```typescript
// Example of a functional component
export const NewComponent = () => {
  return <div>Hello, World!</div>;
};
```

### Error Handling

Utilize the ErrorBoundary component to catch JavaScript errors in child components and display a fallback UI.

```typescript
// Example of using ErrorBoundary
<ErrorBoundary>
  <MyComponent />
</ErrorBoundary>
```

## When to Use

- When creating reusable UI components.
- When implementing error handling for user interactions.

## Commands

```bash
# Start the development server
npm start

# Build the application for production
npm run build
```

## Anti-Patterns

### Don't: Modify shared state directly

Directly modifying shared state can lead to unpredictable UI behavior and bugs.

```typescript
// BAD
state.value = newValue; // This is incorrect
```
<!-- L3:END -->