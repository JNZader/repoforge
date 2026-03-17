---
name: add-docs-prompts-endpoint
description: >
  This skill covers the integration of shared system prompts into your application.
  Trigger: When utilizing the docs_prompts in chapter calls.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Using Index Prompt

Inject the index prompt into your chapter call for structured navigation.

```python
from repoforge.docs_prompts import index_prompt

def get_navigation():
    return index_prompt
```

### Implementing Overview Prompt

Utilize the overview prompt to provide a summary of the chapter's content.

```python
from repoforge.docs_prompts import overview_prompt

def get_overview():
    return overview_prompt
```

## When to Use

- When you need to provide structured prompts for documentation chapters.
- To enhance user experience with clear navigation and summaries.
- During the development of documentation to ensure consistency across chapters.

## Commands

```bash
python repoforge/cli.py generate-docs
python repoforge/cli.py serve-docs
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

| Task                     | Pattern                     |
|--------------------------|-----------------------------|
| Get index prompt         | `index_prompt`              |
| Get overview prompt      | `overview_prompt`           |