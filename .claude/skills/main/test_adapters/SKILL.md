---
name: test-adapters-strip-yaml-frontmatter
description: >
  This skill covers testing the _strip_yaml_frontmatter helper.
  Trigger: When validating YAML frontmatter in test_adapters.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### TestStripYamlFrontmatter

Ensure the _strip_yaml_frontmatter function correctly removes YAML frontmatter from strings.

```python
def test_strip_yaml_frontmatter():
    input_data = "---\ntitle: Test\n---\nContent"
    expected_output = "Content"
    assert TestStripYamlFrontmatter.strip_yaml_frontmatter(input_data) == expected_output
```

### TestSkillNameFromPath

Verify that skill names are correctly derived from file paths.

```python
def test_skill_name_from_path():
    path = "skills/test_adapters.py"
    expected_name = "test-adapters"
    assert TestSkillNameFromPath.from_path(path) == expected_name
```

## When to Use

- When writing tests for YAML processing in test_adapters.
- To validate skill name extraction from file paths.
- During debugging of YAML frontmatter issues in test scenarios.

## Commands

```bash
pytest tests/test_adapters.py
```

## Anti-Patterns

### Don't: Use hardcoded strings

Hardcoded strings can lead to brittle tests that fail on minor changes.

```python
# BAD
def test_hardcoded_string():
    assert TestStripYamlFrontmatter.strip_yaml_frontmatter("---\ntitle: Test\n---\nContent") == "Wrong Content"
```

## Quick Reference

| Task | Pattern |
|------|---------|
| Validate YAML frontmatter | `TestStripYamlFrontmatter` |
| Extract skill name from path | `TestSkillNameFromPath` |