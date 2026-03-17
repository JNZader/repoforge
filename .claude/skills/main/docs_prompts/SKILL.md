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

### Use Index Prompt

Utilize the `index_prompt` to provide a structured introduction to your documentation.

```python
from repoforge.docs_prompts import index_prompt

def generate_index():
    return index_prompt()
```

### Implement Overview Prompt

Incorporate the `overview_prompt` to summarize the key aspects of your project.

```python
from repoforge.docs_prompts import overview_prompt

def generate_overview():
    return overview_prompt()
```

## When to Use

- When generating documentation for a new project chapter.
- To provide a quick start guide for users unfamiliar with the system.
- During the review process to ensure all chapters have consistent prompts.

## Commands

```bash
python repoforge/cli.py generate-docs
python repoforge/cli.py update-prompts
```

## Anti-Patterns

### Don't: Hardcode Prompts

Hardcoding prompts leads to inconsistency and maintenance challenges.

```python
# BAD
def generate_hardcoded_prompt():
    return "This is a hardcoded prompt."
```

## Quick Reference

| Task | Pattern |
|------|---------|
| Generate index | `index_prompt()` |
| Create overview | `overview_prompt()` |