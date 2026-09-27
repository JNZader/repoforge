---
name: auth-layer
description: >
  This layer owns all authentication and authorization logic.
  Trigger: When working in auth/ — adding, modifying, or debugging login,
  token issuance, and permission checks.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Layer Structure

```
auth/
├── src/auth/index.ts — entry point that wires service and controller
├── src/auth/service.ts — core business logic for login, token creation
└── src/auth/controller.ts — HTTP handlers exposing auth endpoints
```

## Critical Patterns

### Export functions with explicit return types

All public functions must declare their return type to aid static analysis.

```typescript
export async function login(
  credentials: { email: string; password: string }
): Promise<{ accessToken: string; refreshToken: string }> {
  // implementation
}
```

### Use async/await for all I/O

Never mix callbacks or `.then()` with `await`; keep the async flow consistent.

```typescript
export async function verifyToken(token: string): Promise<User | null> {
  const payload = await jwt.verifyAsync(token, process.env.JWT_SECRET);
  return payload ? await userRepo.findById(payload.sub) : null;
}
```

## When to Use

- Implement a new login strategy (e.g., OAuth, SSO) within the auth layer.
- Add or modify token payload claims or expiration policies.
- Integrate auth checks into other layers (e.g., guard middleware in the API layer).

## Adding a New Endpoint

1. Create a handler in `src/auth/controller.ts` following the existing naming convention (`<action>Handler`).
2. Wire the handler in `src/auth/index.ts` under the exported router.
3. Implement the business logic in `src/auth/service.ts` and export it.
4. Run `npm test` and verify the new route appears in the integration test suite.

## Commands

```bash
npm run lint          # lint the auth layer
npm test              # run unit & integration tests for auth
npm run build          # compile TypeScript for the auth package
```

## Anti-Patterns

- **Don't**: Hard‑code secrets or JWT keys in source files — they must come from `process.env`.
- **Don't**: Return raw database entities from service functions — expose only DTOs to keep layers decoupled.

## Quick Reference

| Task                     | File                         | Pattern |
|--------------------------|------------------------------|---------|
| Add login handler        | `src/auth/controller.ts`     | `async function loginHandler(req, res)` |
| Create token service     | `src/auth/service.ts`        | `export async function generateToken(user)` |
| Register route           | `src/auth/index.ts`          | `router.post('/login', loginHandler)` |