---
name: test-plugins
description: >
  This skill covers testing patterns for various repository mappings.
  Trigger: Load this skill when working with test_plugins.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: low
  token_estimate: 350
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# test-plugins

This skill covers testing patterns for various repository mappings.

**Trigger**: Load this skill when working with test_plugins.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Map Python repositories | `python_repo_map` |
| Map Node repositories | `node_repo_map` |

## Critical Patterns (Summary)
- **Map Python repositories**: Use `python_repo_map` to structure Python project tests.
- **Map Node repositories**: Utilize `node_repo_map` for Node.js project testing.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Map Python repositories

Use `python_repo_map` to structure Python project tests effectively.

```python
# Example of using python_repo_map
from tests.test_plugins import python_repo_map

def test_python_repo():
    assert python_repo_map() is not None
```

### Map Node repositories

Utilize `node_repo_map` for Node.js project testing to ensure proper integration.

```python
# Example of using node_repo_map
from tests.test_plugins import node_repo_map

def test_node_repo():
    assert node_repo_map() is not None
```

## When to Use

- When creating tests for Python repositories.
- When integrating tests for Node.js repositories.

## Commands

```bash
pytest tests/test_plugins.py
```

## Anti-Patterns

### Don't: Hardcode repository paths

Hardcoding paths reduces flexibility and maintainability of tests.

```python
# BAD
def test_hardcoded_path():
    assert load_repo('/path/to/repo') is not None
```
<!-- L3:END -->