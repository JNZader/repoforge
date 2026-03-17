---
name: add-docs-prompts-endpoint
description: >
  This skill covers the integration of shared system prompts into your application.
  Trigger: When implementing documentation prompts in your project.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Use Index Prompt

Utilize the `index_prompt` to generate the main entry point for documentation.

```python
from repoforge.docs_prompts import index_prompt

def generate_index():
    return index_prompt()
```

### Implement Overview Prompt

Leverage the `overview_prompt` to provide a summary of your project.

```python
from repoforge.docs_prompts import overview_prompt

def generate_overview():
    return overview_prompt()
```

## When to Use

- When creating a structured documentation system for your application.
- To provide users with a quickstart guide using `quickstart_prompt`.
- When needing to classify project types with `classify_project`.

## Commands

```bash
python repoforge/cli.py generate-docs
python repoforge/cli.py update-prompts
```

## Anti-Patterns

### Don't: Hardcode Prompts

Hardcoding prompts reduces flexibility and maintainability in your documentation.

```python
# BAD
def generate_hardcoded_prompt():
    return "This is a hardcoded prompt."
```

## Quick Reference

| Task                     | Pattern                     |
|--------------------------|-----------------------------|
| Generate index prompt    | `index_prompt()`            |
| Create overview section   | `overview_prompt()`         |