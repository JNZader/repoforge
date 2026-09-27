---
name: add-incremental-manifest
description: >
  Manage incremental build manifests for reproducible pipelines.
  Trigger: incremental
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills: [load-manifest, save-manifest]
load_priority: high
---

<!-- L1:START -->
# add-incremental-manifest

Manage incremental build manifests for reproducible pipelines.

**Trigger**: incremental
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Load manifest | `load_manifest(Path)` |
| Save manifest | `save_manifest(Path, manifest)` |
| Detect stale chapters | `stale_chapter_names(get_changed_files(...), ...)` |

## Critical Patterns (Summary)
- **Load & Save Manifest Safely**: Use `load_manifest` with fallback and `save_manifest` to persist changes.
- **Detect Stale Chapters After Git Changes**: Combine `get_git_sha`, `get_changed_files`, `build_chapter_deps`, and `stale_chapter_names`.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Load & Save Manifest Safely

Read an existing `Manifest` (or create a new one) and persist modifications without risking `None` errors.

```python
from pathlib import Path
from repoforge.incremental import load_manifest, save_manifest, Manifest

out_dir = Path("build")
manifest = load_manifest(out_dir) or Manifest()
# modify manifest as needed
manifest_path = save_manifest(out_dir, manifest)
print(f"Manifest written to {manifest_path}")
```

### Detect Stale Chapters After Git Changes

Identify which chapters need rebuilding by comparing the current Git SHA with changed files and chapter dependencies.

```python
from pathlib import Path
from repoforge.incremental import (
    get_git_sha,
    get_changed_files,
    build_chapter_deps,
    stale_chapter_names,
)

repo_root = Path(".")
old_sha = get_git_sha(repo_root)
changed_files = get_changed_files(repo_root, old_sha)

# Example: empty