---
name: add-docs-prompts-endpoint
description: >
  This skill covers the integration of shared system prompts into your application.
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

### Accessing Quickstart Prompt

Utilize the quickstart prompt to guide users through initial setup steps.

```python
from repoforge.docs_prompts import quickstart_prompt

def display_quickstart():
    print(quickstart_prompt)
```

## When to Use

- When generating documentation for a new feature.
- To provide users with a quickstart guide during onboarding.
- When debugging prompt injection in chapter calls.

## Commands

```bash
python repoforge/cli.py generate-docs
python repoforge/cli.py update-prompts
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
| Display quickstart prompt | `quickstart_prompt` |