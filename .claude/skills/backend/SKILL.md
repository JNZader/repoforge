---
name: service-layer
description: >
  This layer implements the core business logic and service interfaces of the
  application. It owns the service classes, data access objects, and API
  handlers that coordinate domain operations.
  Trigger: When working in service/ — adding, modifying, or debugging service
  implementations.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Layer Structure

```
service/
├── api.ts          — defines HTTP route handlers
├── userService.ts  — business logic for user domain
└── userDao.ts      — data‑access layer for user persistence
```

## Critical Patterns

### Service Class Pattern — single responsibility

Each service class encapsulates one domain concept and exposes only the
operations needed by callers.

```ts
// userService.ts
export class UserService {
  constructor(private readonly dao: UserDao) {}

  async getUser(id: string): Promise<User> {
    return this.dao.findById(id);
  }

  async createUser(dto: CreateUserDto): Promise<User> {
    // validation, business rules, then persist
    return this.dao.insert(dto);
  }
}
```

### DAO Isolation Pattern — hide storage details

Data‑access objects expose a minimal CRUD API and hide the underlying database
or ORM implementation.

```ts
// userDao.ts
export class UserDao {
  async findById(id: string): Promise<User> { /* ... */ }
  async insert(dto: CreateUserDto): Promise<User> { /* ... */ }
}
```

## When to Use

- Implement a new domain operation (e.g., “reset password”) inside the
  corresponding service file.
- Add or modify persistence logic without touching business rules.
- Expose a new HTTP endpoint by wiring a route handler to an existing service.

## Adding a New Service

1. Create `service/<entity>Service.ts` and export a class named `<Entity>Service`.
2. Add a matching DAO file `service/<entity>Dao.ts` with `findById`, `insert`,
   `update`, and `delete` methods.
3. Register the service in `service/api.ts` with an Express/Koa route handler.
4. Run the test suite (`npm test`) and verify the new endpoint returns the
   expected JSON payload.

## Commands

```bash
npm run lint          # lint the service layer
npm run test          # execute unit/integration tests for services
npm run build         # compile TypeScript sources
```

## Anti-Patterns

- **Don't**: Mix HTTP request parsing logic inside service methods — it couples
  transport concerns to business logic.
- **Don't**: Access the database directly from a controller — bypasses the DAO
  abstraction and makes testing harder.

## Quick Reference

| Task                     | File                     | Pattern |
|--------------------------|--------------------------|---------|
| Add a new route handler  | `service/api.ts`         | Service Class Pattern |
| Persist a new entity     | `service/<entity>Dao.ts` | DAO Isolation Pattern |
| Business rule implementation | `service/<entity>Service.ts` | Service Class Pattern |