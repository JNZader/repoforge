---
name: build-skill-registry
description: >
  This skill covers the creation of a skill registry for prompts.
  Trigger: When initializing prompts in the system.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Build Skill Registry

Use `build_skill_registry` to create a registry for managing skills.

```python
from repoforge.prompts import build_skill_registry

registry = build_skill_registry()
```

### Use Skill Prompt

Utilize `skill_prompt` to define a specific skill prompt for agents.

```python
from repoforge.prompts import skill_prompt

prompt = skill_prompt("What is your skill?")
```

## When to Use

- When setting up a new prompt system for agents.
- To manage and organize multiple skill prompts.
- During the initialization phase of the application.

## Commands

```bash
python repoforge/cli.py init
python repoforge/cli.py run
```

## Anti-Patterns

### Don't: Hardcode Prompts

Hardcoding prompts reduces flexibility and maintainability in the system.

```python
# BAD
prompt = "This is a hardcoded prompt."
```

## Quick Reference

| Task                     | Pattern                     |
|--------------------------|-----------------------------|
| Create skill registry     | `build_skill_registry()`    |
| Define a skill prompt     | `skill_prompt("text")`      |