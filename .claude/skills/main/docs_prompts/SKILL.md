---
name: add-docs-prompts-endpoint
description: >
  This skill covers the integration of shared system prompts into your documentation.
  Trigger: When utilizing the docs_prompts in chapter calls.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Using Index Prompt

Inject the index prompt into your documentation flow to provide a structured overview.

```python
from repoforge.docs_prompts import index_prompt

def generate_index():
    return index_prompt
```

### Implementing Overview Prompt

Utilize the overview prompt to give users a concise introduction to the documentation.

```python
from repoforge.docs_prompts import overview_prompt

def generate_overview():
    return overview_prompt
```

## When to Use

- When generating documentation for a new chapter.
- To provide users with a quickstart guide for your project.
- During the debugging process to ensure prompts are correctly integrated.

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

| Task                       | Pattern                     |
|----------------------------|-----------------------------|
| Generate index prompt      | `index_prompt`              |
| Create overview section     | `overview_prompt`           |