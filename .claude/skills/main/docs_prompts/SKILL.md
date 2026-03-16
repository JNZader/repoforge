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

Utilize the `index_prompt` to provide a consistent introduction across chapters.

```python
from repoforge.docs_prompts import index_prompt

def inject_index_prompt():
    return index_prompt
```

### Get Chapter Prompts

Leverage `get_chapter_prompts` to retrieve prompts for specific chapters dynamically.

```python
from repoforge.docs_prompts import get_chapter_prompts

def fetch_prompts(chapter):
    return get_chapter_prompts(chapter)
```

## When to Use

- When creating a new documentation chapter that requires a standard introduction.
- To dynamically load prompts based on user-selected chapters.
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
def hardcoded_prompt():
    return "This is a hardcoded prompt."
```

## Quick Reference

| Task                       | Pattern                     |
|----------------------------|-----------------------------|
| Inject index prompt        | `index_prompt`             |
| Retrieve chapter prompts    | `get_chapter_prompts`      |