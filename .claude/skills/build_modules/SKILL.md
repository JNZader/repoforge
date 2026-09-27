---
name: build_modules-layer
description: >
  Build and evaluation layer for generating and testing code modules across multiple languages.
  Contains harness functions for creating FastAPI/Next.js/Go modules, scenario runners, and module adaptors.
  Trigger: When working in build_modules/ directory and its main responsibility is module generation, evaluation, and adaptation.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: medium
  token_estimate: 1200
  dependencies: []
  related_skills: [frontend-layer, backend-layer]
  load_priority: high
---

<!-- L1:START -->
# build_modules-layer

Build and evaluation layer for generating and testing code modules across multiple languages. Contains harness functions for creating FastAPI/Next.js/Go modules, scenario runners, and module adaptors.

**Trigger**: When working in build_modules/ directory — adding, modifying, or debugging module generation, evaluation scenarios, or cross-language adaptors.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Generate FastAPI module | `make_fastapi_crud_module()` |
| Generate Next.js page module | `make_nextjs_page_module()` |
| Run evaluation scenario | `run_scenario("scenario_name")` |
| Adapt skills for LLM | `adapt_for_copilot(skills)` |
| Detect dead code | `detect_dead_code(ast_symbols)` |

## Critical Patterns (Summary)
- **Module Generation**: Use `make_fastapi_crud_module()` / `make_nextjs_page_module()` to generate language-specific module skeletons from a unified interface.
- **Adaptation Layer**: Use `adapt_for_*` functions to normalize skill dicts for different LLM targets (Cursor, Codex, Gemini, Copilot) before generation.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Pattern 1: Module Generation Interface

The harness provides unified functions to generate module skeletons for different languages. Each function returns a tuple of (module_info, module_code) where module_info contains metadata and module_code contains the generated source.

```python
from eval.harness import make_fastapi_crud_module

module_info, module_code = make_fastapi_crud_module()
# module_info: dict with module metadata
# module_code: dict with generated source code per language
```

```python
from eval.harness import make_nextjs_page_module

module_info, module_code = make_nextjs_page_module()
# Generates Next.js page module with file structure and exports
```

### Pattern 2: Cross-Language Adaptation

The `repoforge/adapters.py` module normalizes skill dictionaries for different LLM interfaces. Each adapter function transforms the same skill set into a format optimized for a specific tool.

```python
from repoforge.adapters import adapt_for_copilot

adapted = adapt_for_copilot(skills)
# Returns dict formatted for Copilot's code generation
```

```python
from repoforge.adapters import adapt_for_cursor

adapted = adapt_for_cursor(skills, repo_map)
# Returns dict formatted for Cursor with repo path mapping
```

## When to Use

- Generating new module skeletons for FastAPI, Next.js, or Go services
- Adapting skill dictionaries for different LLM code generation tools
- Running evaluation scenarios to test module quality and pattern detection
- Detecting dead code and analyzing module complexity before generation

## Adding a New Module

1. `eval/harness.py` — Add new `make_*_module()` function following existing pattern
2. `eval/scenarios_real.py` — Add scenario function for the new module type
3. `repoforge/adapters.py` — Add `adapt_for_*` entry if targeting new LLM tool
4. Verify: `python -m eval.harness run_all` to regenerate reports

## Commands

```bash
python -m eval.harness run_all  # Run all evaluation scenarios
python -m eval.harness print_report  # Print evaluation reports
python -c "from eval.harness import make_fastapi_crud_module; make_fastapi_crud_module()"
```

## Anti-Patterns

### Don't: Generate modules without adapting skills for the target LLM

<Why it's wrong:> Using raw skill dicts without adapter transformation causes pattern mismatches and code generation failures. Each LLM tool (Cursor, Codex, Gemini, Copilot) expects different key ordering and format. Always run skills through the appropriate `adapt_for_*` function before passing to code generators.

```python
from repoforge.adapters import adapt_for_copilot

# BAD - raw skills will fail in Copilot
generate_module(skills)  

# GOOD - adapted skills work correctly
generate_module(adapt_for_copilot(skills))
```
<!-- L3:END -->