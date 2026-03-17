---
name: add-docs-prompts-endpoint
description: >
  This skill covers the integration of shared system prompts into your application.
  Trigger: When you need to utilize prompts for documentation generation.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### Use Index Prompt

Utilize the `index_prompt` to generate the main index for your documentation.

```python
from repoforge.docs_prompts import index_prompt

documentation_index = index_prompt()
```

### Get Chapter Prompts

Retrieve chapter-specific prompts using `get_chapter_prompts` for tailored documentation.

```python
from repoforge.docs_prompts import get_chapter_prompts

chapter_prompts = get_chapter_prompts('architecture')
```

## When to Use

- When generating an index for your documentation using shared prompts.
- When retrieving specific prompts for different chapters in your documentation.
- To ensure consistency in documentation across various sections.

## Commands

```bash
python repoforge/cli.py generate-docs
python repoforge/cli.py update-prompts
```

## Anti-Patterns

### Don't: Hardcode Prompts

Hardcoding prompts leads to maintenance issues and inconsistency across documentation.

```python
# BAD
documentation_index = "This is a hardcoded index prompt."
```

## Quick Reference

| Task                       | Pattern                     |
|----------------------------|-----------------------------|
| Generate documentation index| `index_prompt()`            |
| Retrieve chapter prompts    | `get_chapter_prompts('chapter_name')` |