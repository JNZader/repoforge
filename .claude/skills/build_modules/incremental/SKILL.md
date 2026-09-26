---
name: extend-incremental-model
description: >
  Provides patterns for managing incremental manifests and detecting changes.
  Trigger: incremental data model updates.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills: [load-manifest, git-integration]
load_priority: high
---

<!-- L1:START -->
# extend-incremental-model

Manage incremental manifests and change detection in a reproducible way.

**Trigger**: when the `incremental` data model is read or updated.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Load a manifest | `manifest = load_manifest(Path("manifest.json"))` |
| Save a manifest | `save_manifest(Path("manifest.json"), manifest)` |
| List changed files | `changed = get_changed_files(get_git_sha())` |

## Critical Patterns (Summary)
- **Load & Save Manifest**: use `load_manifest` / `save_manifest` with `Manifest` objects.
- **Detect Changed Files**: combine `get_git_sha` and `get_changed_files` for reliable diffing.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Load & Save Manifest

Persist and retrieve the full `Manifest` safely, avoiding manual JSON handling.

```python
from pathlib import Path
from repoforge.incremental import load_manifest, save_manifest, Manifest

manifest_path = Path("manifest.json")
manifest: Manifest = load_manifest(manifest_path)

# ... modify manifest ...

save_manifest(manifest_path, manifest)
```

### Detect Changed Files

Leverage Git SHA to compute the set of files that have changed since the last commit.

```python
from repoforge.incremental import get_git_sha, get_changed_files

current_sha = get_git_sha()
changed_files = get_changed_files(current_sha)
print(f"Changed since {current_sha}: {changed_files}")
```

## When to Use

- Building a new release where only modified chapters should be re‑processed.
- Running CI pipelines that need to skip unchanged files.
- Debugging incremental builds by inspecting the manifest state.

## Commands

```bash
python -m repoforge.cli build          # run the incremental build process
docker build . -t repoforge:latest      # containerize the build environment
```

## Anti-Patterns

### Don't: Re‑implement content hashing manually

Re‑creating hash logic bypasses the module’s canonical `content_hash` utility and can diverge from the stored manifest.

```python
# BAD
import hashlib
def bad_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
```
<!-- L3:END -->