---
name: manage-database-session
description: >
  This skill covers patterns for managing database sessions and models.
  Trigger: When working with database interactions in the backend.
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
# manage-database-session

This skill covers patterns for managing database sessions and models.

**Trigger**: When working with database interactions in the backend.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Create a database model | `Base` |
| Get a database session | `get_db` |

## Critical Patterns (Summary)
- **Create a database model**: Use `Base` to define your database models.
- **Get a database session**: Utilize `get_db` to retrieve a database session for operations.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Create a database model

Define your database models by extending the `Base` class.

```python
from apps.server.app.models.database import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
```

### Get a database session

Use the `get_db` function to obtain a database session for your operations.

```python
from apps.server.app.models.database import get_db
from fastapi import Depends

def read_users(db: Session = Depends(get_db)):
    return db.query(User).all()
```

## When to Use

- When defining new database models for your application.
- When you need to retrieve a session for database operations.

## Commands

```bash
pip install sqlalchemy
```

## Anti-Patterns

### Don't: Use raw SQL queries directly

Using raw SQL queries can lead to SQL injection vulnerabilities and makes your code harder to maintain.

```python
# BAD
db.execute("SELECT * FROM users WHERE name = '" + user_input + "'")
```
<!-- L3:END -->