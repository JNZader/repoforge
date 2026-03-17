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

Utilize the `index_prompt` to provide a structured introduction to your documentation.

```python
from repoforge.docs_prompts import index_prompt

def inject_index():
    return index_prompt
```

### Implement Overview Prompt

Incorporate the `overview_prompt` to summarize the key aspects of your documentation.

```python
from repoforge.docs_prompts import overview_prompt

def inject_overview():
    return overview_prompt
```

## When to Use

- When creating a new chapter in your documentation.
- To provide a consistent introduction across multiple sections.
- During the review process to ensure clarity and coherence.

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
def inject_without_prompts():
    return "This is a chapter without prompts."
```

## Quick Reference

| Task | Pattern |
|------|---------|
| Inject index prompt | `index_prompt` |
| Use overview prompt | `overview_prompt` |