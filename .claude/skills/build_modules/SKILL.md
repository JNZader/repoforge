---
name: build_modules-layer
description: >
  Generates and caches code modules for FastAPI, Next.js, Go services, and mixed layers.
  It orchestrates module factories, snapshot caching, and impact analysis.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: medium
token_estimate: 340
dependencies: []
related_skills:
  - frontend-layer
  - backend-layer
load_priority: high
---

<!-- L1:START -->
# build_modules-layer

Creates all build‑time modules (FastAPI CRUD, Next.js pages, Go services, mixed layers) and manages incremental caching.

**Trigger**: When working in the `build_modules/` directory — adding, modifying, or debugging module generation logic.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Add a new FastAPI CRUD module | `make_fastapi_crud_module` |
| Update cache after code change | `hash_content` → `compute_repo_snapshot` |
| Compute blast radius for a commit | `blast_radius_from_commit` |

## Critical Patterns (Summary)
- **Module Factory Pattern**: Use exported `make_*_module` helpers to keep generation consistent.
- **Incremental Cache Pattern**: Hash content & diff snapshots to avoid full regeneration.
<!-- L2:END -->

<!-- L3:START -->
## Layer Structure

```
./
├── eval/harness.py — entry point, exports make_*_module helpers
├── repoforge/cache.py — hashing & snapshot diff utilities
└── repoforge/blast_radius.py — impact analysis for changes
```

## Critical Patterns (Detailed)

### Module Factory Pattern

All generated modules must be created via the factory helpers in `eval/harness.py`.  
This guarantees uniform naming, routing, and dependency injection.

```python
from eval.harness import make_fastapi_crud_module, make_nextjs_page_module

# FastAPI CRUD endpoint for a new model
crud_module = make_fastapi_crud_module(model_name="User", schema=UserSchema)

# Next.js page for the same model
page_module = make_nextjs_page_module(model_name="User")
```

### Incremental Cache Pattern

Before regenerating modules, compute a content hash and compare snapshots.  
Only changed files trigger regeneration, keeping builds fast.

```python
from repoforge.cache import hash_content, compute_repo_snapshot, diff_snapshots

# Hash a source file
file_hash = hash_content(open("repoforge/adapters.py").read())

# Take a repo snapshot
snapshot = compute_repo_snapshot(root_path=".")

# Detect changes since last run
changed = diff_snapshots(previous_snapshot, snapshot)
if changed:
    # regenerate affected modules
    ...
```

## When to Use

- Adding a new backend service (FastAPI, Go) or frontend page (Next.js) via the layer.
- Updating existing module logic and needing fast, incremental rebuilds.
- Assessing the blast radius of a commit to decide which modules must be regenerated.

## Commands

```bash
# Run the harness with a real scenario (generates all modules)
python -m eval.harness --scenario real

# Show cache diff after a code change
python -c "from repoforge.cache import compute_repo_snapshot, diff_snapshots; \
print(diff_snapshots(prev, compute_repo_snapshot('.')))"
```

## Anti-Patterns

### Don't: Modify generated module files directly

Changing files produced by `make_*_module` breaks the deterministic cache and invalidates blast‑radius calculations, causing downstream layers (frontend, backend) to diverge.

```python
# BAD: editing a generated file
with open("generated/user_crud.py", "a") as f:
    f.write("# manual tweak")  # <-- leads to cache mismatch
```
<!-- L3:END -->