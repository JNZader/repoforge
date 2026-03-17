---
name: test-adapters-helper
description: >
  This skill covers testing patterns for the _strip_yaml_frontmatter helper.
  Trigger: When testing YAML frontmatter stripping in adapters.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### TestStripYamlFrontmatter

Ensure the _strip_yaml_frontmatter function correctly removes YAML frontmatter.

```python
def test_strip_yaml_frontmatter():
    assert TestStripYamlFrontmatter().strip('---\ntitle: Test\n---\nContent') == 'Content'
```

### TestSkillNameFromPath

Verify that skill names are correctly derived from file paths.

```python
def test_skill_name_from_path():
    assert TestSkillNameFromPath().get_name('path/to/skill_file.py') == 'skill_file'
```

## When to Use

- When validating the output of YAML frontmatter processing.
- When ensuring skill names are accurately extracted from file paths.
- To debug issues related to incorrect YAML parsing in tests.

## Commands

```bash
pytest tests/test_adapters.py
```

## Anti-Patterns

### Don't: Ignore Test Coverage

Neglecting test coverage can lead to untested code paths and potential bugs.

```python
# BAD
def test_untested_function():
    pass  # No assertions or checks
```

## Quick Reference

| Task | Pattern |
|------|---------|
| Test YAML stripping | `TestStripYamlFrontmatter` |
| Validate skill name extraction | `TestSkillNameFromPath` |