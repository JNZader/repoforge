---
name: main-layer
description: >
  This layer encompasses the core functionality of the project, managing the main application logic and integrations.
  Trigger: When working in main/ — adding, modifying, or debugging core functionalities.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: medium
  token_estimate: 800
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# main-layer

This skill covers the core functionalities and integrations of the project.

**Trigger**: When working in main/ directory and its main responsibility.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Create a new module | `eval/harness.py` |

## Critical Patterns (Summary)
- **Module Creation**: Follow the structure in `eval/harness.py` for new module exports.
- **Data Handling**: Use `repoforge/compressor.py` for managing data models.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Module Creation

When creating a new module, ensure to follow the export conventions established in `eval/harness.py`.

```python
# eval/harness.py
def make_fastapi_crud_module():
    # Implementation here
```

### Data Handling

Utilize the data model defined in `repoforge/compressor.py` for consistent data management across the application.

```python
# repoforge/compressor.py
class SkillCompressor:
    def compress_file(self, file_path):
        # Compression logic here
```

## When to Use

- When adding new functionalities to the core application.
- When integrating external services or modules.

## Commands

```bash
python -m eval.harness
python -m repoforge.cli
```

## Anti-Patterns

### Don't: Modify core logic without testing

Changing core functionalities without proper testing can lead to application instability.

```python
# BAD
def main_logic():
    # Directly modifying core behavior without tests
```
<!-- L3:END -->