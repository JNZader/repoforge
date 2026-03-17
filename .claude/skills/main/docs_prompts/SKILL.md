---
name: add-docs-prompts-endpoint
description: >
  This skill covers the integration of shared system prompts into your documentation.
  Trigger: When utilizing the `docs_prompts` for chapter calls.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Using Index Prompt

Inject the `index_prompt` to provide a structured entry point for documentation.

```python
from repoforge.docs_prompts import index_prompt

def generate_index():
    return index_prompt
```

### Implementing Overview Prompt

Utilize the `overview_prompt` to summarize the documentation effectively.

```python
from repoforge.docs_prompts import overview_prompt

def generate_overview():
    return overview_prompt
```

## When to Use

- When creating a new chapter in the documentation.
- To provide a consistent overview across multiple sections.
- During the review process to ensure all chapters have necessary prompts.

## Commands

```bash
python repoforge/cli.py generate-docs
python repoforge/cli.py update-prompts
```

## Anti-Patterns

### Don't: Skip Prompt Integration

Neglecting to integrate prompts can lead to disjointed documentation. 

```python
# BAD
def generate_documentation():
    return "This is a documentation without prompts."
```

## Quick Reference

| Task | Pattern |
|------|---------|
| Generate index | `index_prompt` |
| Create overview | `overview_prompt` |