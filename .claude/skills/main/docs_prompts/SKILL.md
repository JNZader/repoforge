---
name: get-chapter-prompts
description: >
  This skill covers the generation of chapter prompts for documentation.
  Trigger: Load this skill when working with docs_prompts.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: low
  token_estimate: 250
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# get-chapter-prompts

This skill covers the generation of chapter prompts for documentation.

**Trigger**: Load this skill when working with docs_prompts.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task                     | Pattern                     |
|--------------------------|-----------------------------|
| Generate index prompt    | `index_prompt`              |
| Generate overview prompt  | `overview_prompt`           |

## Critical Patterns (Summary)
- **Generate index prompt**: Use `index_prompt` to create an index for documentation.
- **Generate overview prompt**: Use `overview_prompt` to create an overview section for documentation.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Generate index prompt

Use `index_prompt` to create an index for documentation, providing a structured overview of the content.

```python
index = index_prompt()
```

### Generate overview prompt

Use `overview_prompt` to create an overview section for documentation, summarizing key points.

```python
overview = overview_prompt()
```

## When to Use

- When creating structured documentation for a project.
- When needing to summarize content for user guides.

## Commands

```bash
python repoforge/cli.py generate-docs
```

## Anti-Patterns

### Don't: Hardcode prompts

Hardcoding prompts reduces flexibility and maintainability.

```python
# BAD
index = "This is a hardcoded index."
```
<!-- L3:END -->