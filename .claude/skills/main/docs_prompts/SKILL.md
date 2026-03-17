---
name: add-docs-prompts-endpoint
description: >
  This skill covers the integration of shared system prompts into your application.
  Trigger: When you need to utilize prompts from the docs_prompts module.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Using Index Prompt

Utilize the `index_prompt` to generate the index for your documentation.

```python
from repoforge.docs_prompts import index_prompt

def generate_index():
    return index_prompt()
```

### Accessing Overview Prompt

Leverage the `overview_prompt` to provide a summary of your documentation.

```python
from repoforge.docs_prompts import overview_prompt

def get_overview():
    return overview_prompt()
```

## When to Use

- When generating documentation for a new feature.
- To provide a quick start guide for users.
- When needing to classify project types based on prompts.

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
def get_hardcoded_prompt():
    return "This is a hardcoded prompt."
```

## Quick Reference

| Task                       | Pattern                     |
|----------------------------|-----------------------------|
| Generate index             | `index_prompt()`            |
| Get overview               | `overview_prompt()`         |