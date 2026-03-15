---
name: add-docs-prompts-endpoint
description: >
  This skill covers the integration of shared system prompts into your documentation.
  Trigger: When implementing documentation prompts in your project.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Use Index Prompt

Utilize the `index_prompt` to generate a structured index for your documentation.

```python
from repoforge.docs_prompts import index_prompt

index = index_prompt()
```

### Implement Overview Prompt

Leverage the `overview_prompt` to provide a concise summary of your project.

```python
from repoforge.docs_prompts import overview_prompt

overview = overview_prompt()
```

## When to Use

- When creating a new documentation chapter.
- To provide a quick start guide for users.
- During the review of documentation for clarity and completeness.

## Commands

```bash
python repoforge/cli.py generate-docs
python repoforge/cli.py update-prompts
```

## Anti-Patterns

### Don't: Skip Core Mechanisms Prompt

Neglecting the `core_mechanisms_prompt` can lead to incomplete documentation.

```python
# BAD
from repoforge.docs_prompts import overview_prompt

# Missing core mechanisms
overview = overview_prompt()
```

## Quick Reference

| Task | Pattern |
|------|---------|
| Generate index | `index_prompt()` |
| Create overview | `overview_prompt()` |