---
name: add-docs-prompts-endpoint
description: >
  This skill covers the integration of shared system prompts into your documentation.
  Trigger: When you need to inject prompts into chapter calls.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Using Index Prompt

Inject the index prompt to provide a structured overview of the documentation.

```python
from repoforge.docs_prompts import index_prompt

def get_documentation_index():
    return index_prompt
```

### Implementing Overview Prompt

Utilize the overview prompt to summarize the key aspects of the documentation.

```python
from repoforge.docs_prompts import overview_prompt

def get_documentation_overview():
    return overview_prompt
```

## When to Use

- When structuring the documentation for a new project.
- To provide a summary at the beginning of each chapter.
- During the review process to ensure all chapters are aligned with the prompts.

## Commands

```bash
python repoforge/cli.py generate-docs
python repoforge/cli.py validate-prompts
```

## Anti-Patterns

### Don't: Hardcode Prompts

Hardcoding prompts reduces flexibility and maintainability of the documentation.

```python
# BAD
def get_hardcoded_prompt():
    return "This is a hardcoded prompt."
```

## Quick Reference

| Task | Pattern |
|------|---------|
| Inject index prompt | `index_prompt` |
| Summarize documentation | `overview_prompt` |