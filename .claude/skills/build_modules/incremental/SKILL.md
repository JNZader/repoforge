---
name: add-incremental-endpoint
description: >
  Incremental manifest management for chapter dependencies.
  Trigger: incremental or manifest operations
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: medium
  token_estimate: 450
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# add-incremental-endpoint

Incremental manifest management for chapter dependencies.

**Trigger**: incremental or manifest operations
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Load manifest | `load_manifest(out_dir)` |
| Get git SHA | `get_git_sha(repo_root)` |
| Find stale chapters | `stale_chapter_names(changed_files, consumed_by_chapter)` |
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Summary)

### load_manifest + save_manifest

<One sentence: Loads/saves the chapter manifest JSON for incremental rebuild tracking.>

```python
# Load existing manifest
manifest = load_manifest(out_dir)

# Save updated manifest after changes
save_manifest(out_dir, manifest)
```

### get_changed_files + build_chapter_deps

<One sentence: Computes which files changed since last SHA and maps chapter dependencies.>

```python
# Get files changed since last build
changed = get_changed_files(repo_root, old_sha)

# Build dependency graph for chapters
deps = build_chapter_deps(repo_map, chapters)
```
<!-- L3:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### load_manifest + save_manifest

Loads the chapter manifest JSON from `out_dir` or saves an updated manifest after incremental changes. Uses the `Manifest` dataclass for type-safe access.

```python
from repoforge.incremental import load_manifest, save_manifest, Manifest

manifest: Manifest = load_manifest(out_dir)
# ... modify manifest ...
save_manifest(out_dir, manifest)
```

### get_changed_files + build_chapter_deps

Computes which files changed since the last git SHA and maps chapter dependency relationships. `get_changed_files` returns a `list[str]` of file paths modified since `old_sha`. `build_chapter_deps` takes a `repo_map: dict` and `chapters: list[dict]` returning `dict[str, list[str]]` of chapter-to-dependency mappings.

```python
changed: list[str] = get_changed_files(repo_root, old_sha)
deps: dict[str, list[str]] = build_chapter_deps(repo_map, chapters)
```
<!-- L3:END -->

<!-- L3:START -->
## When to Use

- After git operations to detect which files changed since last build
- Before rebuilding chapters to determine which need re-rendering
- When tracking incremental state across builds

## Commands

```bash
python -m repoforge.cli build --incremental
docker build --pull --no-cache
```
<!-- L3:END -->

<!-- L3:START -->
## Anti-Patterns

### Don't: Skip manifest persistence after chapter edits

<Why it's wrong: Without calling `save_manifest`, the incremental state is lost and full rebuilds are triggered unnecessarily.>

```python
# BAD: Forgetting to persist manifest
# save_manifest(out_dir, manifest)  # missing!
```
<!-- L3:END -->

<!-- L3:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Get git SHA | `get_git_sha(repo_root)` |
| Find stale chapters | `stale_chapter_names(changed_files, consumed_by_chapter)` |
| Cite files in prompt | `files_cited_in_prompt(prompt, known_files)` |
<!-- L3:END -->
<!-- L3:END -->