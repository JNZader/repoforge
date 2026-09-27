---
name: add-incremental-manifest
description: >
  Manage incremental build state for repoforge projects.
  Trigger: when working with incremental manifests.
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
# add-incremental-manifest

Manage incremental build state for repoforge projects.

**Trigger**: when working with incremental manifests.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Load manifest | `load_manifest(out_dir)` |
| Save manifest | `save_manifest(out_dir, manifest)` |
| Find stale chapters | `stale_chapter_names(changed, deps)` |

## Critical Patterns (Summary)
- **Load & Save Manifest Safely**: Use `load_manifest` and `save_manifest` with proper Path handling.
- **Detect Stale Chapters via Git SHA**: Combine `get_git_sha`, `get_changed_files`, and `stale_chapter_names`.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Load & Save Manifest Safely

Persist and retrieve the build manifest without corrupting data. Always validate the returned value before use.

```python
from pathlib import Path
from repoforge.incremental import load_manifest, save_manifest, Manifest

out_dir = Path("./build")
manifest: Manifest | None = load_manifest(out_dir)
if manifest is None:
    manifest = Manifest()  # assume dataclass default
# ... modify manifest ...
manifest_path = save_manifest(out_dir, manifest)
print(f"Manifest saved to {manifest_path}")
```

### Detect Stale Chapters via Git SHA

Identify chapters that need rebuilding by comparing the current Git SHA with the previous one and walking dependency graphs.

```python
from pathlib import Path
from repoforge.incremental import (
    get_git_sha,
    get_changed_files,
    build_chapter_deps,
    stale_chapter_names,
)

repo_root = Path(".")
old_sha = "a1b2c3d4"  # previous build SHA
new_sha = get_git_sha(repo_root)
changed = get_changed_files(repo_root, old_sha)

# repo_map and chapters would come from your project config
deps = build_chapter_deps(repo_map={}, chapters=[])
stale = stale_chapter_names(changed, deps)
print(f"Stale chapters: {stale}")
```

## When to Use

- When a CI pipeline needs to rebuild only affected chapters after a code change.
- When generating incremental documentation and you must avoid reprocessing unchanged sections.
- When debugging stale‑chapter detection failures.

## Commands

```bash
# Run the incremental build inside Docker
docker build -t repoforge .
docker run --rm -v "$(pwd)":/app repoforge python -m repoforge.cli build

# Direct Python invocation
python -m repoforge.cli build --incremental
```

## Anti-Patterns

### Don't: Mutate Manifest without saving

Modifying the in‑memory `Manifest` and forgetting to persist it leads to out‑of‑sync builds.

```python
manifest = load_manifest(Path("./build"))
manifest.some_field = "new value"
# BAD: never call save_manifest, changes are lost on next run
```
<!-- L3:END -->