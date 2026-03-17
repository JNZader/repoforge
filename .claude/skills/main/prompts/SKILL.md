---
name: add-prompts-endpoint
description: >
  This skill covers the integration of various prompt types into the system.
  Trigger: When working with prompts in the application.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Using skill_prompt

Utilize `skill_prompt` to define a new skill prompt for the system.

```python
from repoforge.prompts import skill_prompt

new_skill = skill_prompt("example_skill", "This is an example skill prompt.")
```

### Building a skill registry

Leverage `build_skill_registry` to create a registry of all defined skills.

```python
from repoforge.prompts import build_skill_registry

registry = build_skill_registry([new_skill])
```

## When to Use

- When defining new skills for the application using prompts.
- To create a centralized registry of skills for easier management.
- When integrating prompts into various layers of the application.

## Commands

```bash
python repoforge/cli.py add-prompts-endpoint
```

## Anti-Patterns

### Don't: Overuse hooks_prompt

Overusing `hooks_prompt` can lead to complex and unmanageable code. 

```python
from repoforge.prompts import hooks_prompt

# BAD: Excessive use of hooks leading to confusion
hooks_prompt("hook1", "First hook")
hooks_prompt("hook2", "Second hook")
```

## Quick Reference

| Task                     | Pattern                     |
|--------------------------|-----------------------------|
| Define a new skill prompt| `skill_prompt(...)`         |
| Create a skill registry   | `build_skill_registry(...)` |