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

### Use Index Prompt

Utilize the `index_prompt` to provide a structured entry point for your documentation.

```python
from repoforge.docs_prompts import index_prompt

def generate_index():
    return index_prompt()
```

### Implement Overview Prompt

Leverage the `overview_prompt` to summarize the key aspects of your documentation.

```python
from repoforge.docs_prompts import overview_prompt

def generate_overview():
    return overview_prompt()
```

## When to Use

- When creating a new chapter in your documentation.
- To provide a quick reference for users navigating through the documentation.
- During the review process to ensure all chapters have consistent prompts.

## Commands

```bash
python repoforge/cli.py generate-docs
python repoforge/cli.py update-prompts
```

## Anti-Patterns

### Don't: Skip Prompt Integration

Neglecting to integrate prompts can lead to disjointed documentation and user confusion.

```python
# BAD
def generate_chapter():
    return "This is a chapter without prompts."
```

## Quick Reference

| Task                     | Pattern                     |
|--------------------------|-----------------------------|
| Generate index prompt    | `index_prompt()`            |
| Create overview section   | `overview_prompt()`         |