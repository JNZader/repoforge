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

### Use Index Prompt

Inject the index prompt into your chapter call to provide a structured overview.

```python
from repoforge.docs_prompts import index_prompt

def chapter_call():
    return index_prompt
```

### Get Chapter Prompts

Retrieve all chapter prompts for dynamic content generation.

```python
from repoforge.docs_prompts import get_chapter_prompts

def fetch_prompts():
    return get_chapter_prompts()
```

## When to Use

- When you need to provide a consistent introduction across multiple chapters.
- To dynamically generate content based on chapter-specific prompts.
- During the development of documentation to ensure clarity and structure.

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
def chapter_call():
    return "This is a hardcoded prompt."
```

## Quick Reference

| Task                     | Pattern                     |
|--------------------------|-----------------------------|
| Retrieve chapter prompts  | `get_chapter_prompts()`     |
| Use index prompt          | `index_prompt`              |