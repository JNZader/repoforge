"""
eval/harness.py - Prompt evaluation harness for RepoForge.

Runs prompts against synthetic repo snapshots and scores SKILL.md / AGENT.md
output quality across 4 dimensions:
  1. Trigger precision   - are triggers specific enough to avoid false positives?
  2. Code concreteness   - do examples reference actual paths/exports from the module?
  3. Pattern detection   - do conventions reflect real patterns found in the code?
  4. Multilang coverage  - does a skill cover all languages present in its layer?

Usage:
  python -m eval.harness                         # run all scenarios
  python -m eval.harness --scenario fastapi_crud # run one scenario
  python -m eval.harness --compare v1 v2         # diff two prompt versions
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# Add parent to path when running directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from repoforge.prompts import agent_prompt, layer_skill_prompt, skill_prompt

# ---------------------------------------------------------------------------
# Synthetic repo snapshots (no real repos needed)
# ---------------------------------------------------------------------------

def make_fastapi_crud_module() -> tuple[dict, dict]:
    """A FastAPI CRUD router — most common backend pattern."""
    module = {
        "path": "app/routers/items.py",
        "name": "items",
        "language": "Python",
        "exports": ["router", "get_items", "get_item", "create_item", "update_item", "delete_item"],
        "imports": ["fastapi", "sqlalchemy", "pydantic"],
        "summary_hint": "CRUD endpoints for the Item resource",
    }
    repo_map = {
        "root": "/repo",
        "tech_stack": ["Python", "FastAPI", "Docker"],
        "entry_points": ["app/main.py"],
        "config_files": ["pyproject.toml", "docker-compose.yml", ".env.example"],
        "layers": {
            "backend": {
                "path": "app",
                "modules": [
                    module,
                    {
                        "path": "app/models/item.py",
                        "name": "item",
                        "language": "Python",
                        "exports": ["Item", "ItemCreate", "ItemUpdate"],
                        "imports": ["sqlalchemy", "pydantic"],
                        "summary_hint": "SQLAlchemy model and Pydantic schemas for Item",
                    },
                    {
                        "path": "app/db/session.py",
                        "name": "session",
                        "language": "Python",
                        "exports": ["get_db", "SessionLocal"],
                        "imports": ["sqlalchemy"],
                        "summary_hint": "Database session factory and dependency",
                    },
                ],
            }
        },
        "stats": {"total_files": 24, "rg_available": True, "rg_version": "ripgrep 14.1.0"},
    }
    return module, repo_map


def make_nextjs_page_module() -> tuple[dict, dict]:
    """A Next.js page component — most common frontend pattern."""
    module = {
        "path": "apps/web/app/dashboard/page.tsx",
        "name": "page",
        "language": "TypeScript",
        "exports": ["default", "generateMetadata"],
        "imports": ["react", "next", "@/components/ui", "@/lib/api"],
        "summary_hint": "Dashboard page with server-side data fetching",
    }
    repo_map = {
        "root": "/repo",
        "tech_stack": ["Next.js", "React", "TypeScript", "Python", "FastAPI"],
        "entry_points": ["apps/web/app/page.tsx", "apps/api/main.py"],
        "config_files": ["package.json", "pyproject.toml", "turbo.json"],
        "layers": {
            "frontend": {
                "path": "apps/web",
                "modules": [
                    module,
                    {
                        "path": "apps/web/components/ui/Button.tsx",
                        "name": "Button",
                        "language": "TypeScript",
                        "exports": ["Button", "ButtonProps"],
                        "imports": ["react", "class-variance-authority"],
                        "summary_hint": "Reusable button component with variants",
                    },
                    {
                        "path": "apps/web/lib/api.ts",
                        "name": "api",
                        "language": "TypeScript",
                        "exports": ["fetchItems", "createItem", "updateItem"],
                        "imports": ["axios"],
                        "summary_hint": "API client functions for backend communication",
                    },
                ],
            },
            "backend": {
                "path": "apps/api",
                "modules": [],
            },
        },
        "stats": {"total_files": 87, "rg_available": True, "rg_version": "ripgrep 14.1.0"},
    }
    return module, repo_map


def make_mixed_layer() -> tuple[str, dict, dict]:
    """A shared package with Python + TypeScript — tests multilang coverage."""
    layer_name = "shared"
    layer = {
        "path": "packages/shared",
        "modules": [
            {
                "path": "packages/shared/types.ts",
                "name": "types",
                "language": "TypeScript",
                "exports": ["User", "Item", "ApiResponse", "PaginatedResponse"],
                "imports": [],
                "summary_hint": "Shared TypeScript type definitions",
            },
            {
                "path": "packages/shared/validators.py",
                "name": "validators",
                "language": "Python",
                "exports": ["validate_email", "validate_uuid", "validate_pagination"],
                "imports": ["pydantic", "re"],
                "summary_hint": "Shared validation utilities used by both API and workers",
            },
            {
                "path": "packages/shared/constants.ts",
                "name": "constants",
                "language": "TypeScript",
                "exports": ["API_VERSION", "DEFAULT_PAGE_SIZE", "ERROR_CODES"],
                "imports": [],
                "summary_hint": "Shared constants used across frontend and backend",
            },
        ],
    }
    repo_map = {
        "root": "/repo",
        "tech_stack": ["Next.js", "React", "TypeScript", "Python", "FastAPI"],
        "entry_points": ["apps/web/app/page.tsx", "apps/api/main.py"],
        "config_files": ["package.json", "pyproject.toml", "turbo.json"],
        "layers": {
            "frontend": {"path": "apps/web", "modules": []},
            "backend": {"path": "apps/api", "modules": []},
            "shared": layer,
        },
        "stats": {"total_files": 42, "rg_available": True},
    }
    return layer_name, layer, repo_map


def make_go_service_module() -> tuple[dict, dict]:
    """A Go HTTP handler — tests non-Python/TS language support."""
    module = {
        "path": "internal/handlers/user.go",
        "name": "user",
        "language": "Go",
        "exports": ["UserHandler", "NewUserHandler", "ListUsers", "GetUser", "CreateUser"],
        "imports": ["net/http", "github.com/gin-gonic/gin", "gorm.io/gorm"],
        "summary_hint": "HTTP handlers for user resource",
    }
    repo_map = {
        "root": "/repo",
        "tech_stack": ["Go", "Docker"],
        "entry_points": ["cmd/server/main.go"],
        "config_files": ["go.mod", "Dockerfile", "docker-compose.yml"],
        "layers": {
            "backend": {
                "path": "internal",
                "modules": [
                    module,
                    {
                        "path": "internal/models/user.go",
                        "name": "user",
                        "language": "Go",
                        "exports": ["User", "UserRepository", "NewUserRepository"],
                        "imports": ["gorm.io/gorm"],
                        "summary_hint": "User model and repository",
                    },
                ],
            }
        },
        "stats": {"total_files": 31, "rg_available": True},
    }
    return module, repo_map


SCENARIOS = {
    "fastapi_crud": lambda: ("module", *make_fastapi_crud_module()),
    "nextjs_page": lambda: ("module", *make_nextjs_page_module()),
    "mixed_layer": lambda: ("layer", *make_mixed_layer()),
    "go_service": lambda: ("module", *make_go_service_module()),
}


# ---------------------------------------------------------------------------
# Scoring rubrics
# ---------------------------------------------------------------------------

@dataclass
class ScoreResult:
    dimension: str
    score: float = 0.0    # 0.0 - 1.0
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def grade(self) -> str:
        if self.score >= 0.85:
            return "✅"
        if self.score >= 0.60:
            return "⚠️ "
        return "❌"


def score_trigger_precision(output: str, module: dict) -> ScoreResult:
    """
    Triggers should be:
    - Specific (contain domain words, not just 'add feature' or 'write code')
    - Varied (not all starting with the same verb)
    - Grounded in the module's actual purpose
    """
    result = ScoreResult(dimension="trigger_precision")

    # Extract triggers: try YAML triggers: list first, then Trigger: inside description
    triggers = re.findall(r"triggers:\s*\n((?:\s+-[^\n]+\n?)+)", output)
    if triggers:
        trigger_lines = re.findall(r"-\s*(.+)", triggers[0])
    else:
        # Fallback: extract Trigger: line from description block
        trigger_match = re.search(r"Trigger:\s*(.+?)(?:\n|$)", output)
        # Also look for "## When to Use" section items as triggers
        when_section = re.search(r"## When to Use(.*?)(?=##|\Z)", output, re.DOTALL)
        trigger_lines = []
        if trigger_match:
            trigger_lines.append(trigger_match.group(1).strip())
        if when_section:
            trigger_lines.extend(re.findall(r"-\s*(.+)", when_section.group(1)))

    if not trigger_lines:
        result.failed.append("No triggers found (neither triggers: block nor Trigger:/When to Use)")
        result.score = 0.0
        return result
    if len(trigger_lines) < 3:
        result.failed.append(f"Only {len(trigger_lines)} triggers, expected ≥3")

    # Check for vague triggers
    vague_patterns = [
        r"^(add|write|create|make|implement)\s+(a\s+)?(new\s+)?feature",
        r"^(fix|update|change)\s+(the\s+)?code",
        r"^work(ing)?\s+on",
        r"^need(ing)?\s+to",
    ]
    vague_count = 0
    for t in trigger_lines:
        if any(re.match(p, t.lower().strip()) for p in vague_patterns):
            vague_count += 1
            result.failed.append(f"Vague trigger: '{t.strip()}'")

    # Check triggers reference domain concepts from module
    domain_words = set()
    for export in module.get("exports", []):
        # Split camelCase / snake_case into words
        words = re.split(r"[_A-Z]", export)
        domain_words.update(w.lower() for w in words if len(w) > 3)
    domain_words.update(w.lower() for w in module.get("imports", []) if len(w) > 3)
    if module.get("summary_hint"):
        domain_words.update(module["summary_hint"].lower().split())

    trigger_text = " ".join(trigger_lines).lower()
    domain_hits = sum(1 for w in domain_words if w in trigger_text)
    if domain_hits >= 2:
        result.passed.append(f"Triggers reference domain concepts ({domain_hits} hits)")
    else:
        result.failed.append("Triggers don't reference module's domain concepts")

    # Check trigger variety (first words)
    first_words = [t.strip().split()[0].lower() for t in trigger_lines if t.strip()]
    if len(set(first_words)) >= len(first_words) * 0.7:
        result.passed.append("Good trigger variety (varied first verbs)")
    else:
        result.failed.append("Low trigger variety (many start with same verb)")

    passed = len(result.passed)
    total = passed + len(result.failed)
    result.score = passed / total if total > 0 else 0.0
    return result


def score_code_concreteness(output: str, module: dict) -> ScoreResult:
    """
    Examples and key files should reference actual paths and exports from the module.
    """
    result = ScoreResult(dimension="code_concreteness")

    # Check that actual file paths appear in the output
    module_path = module.get("path", "")
    if module_path and module_path in output:
        result.passed.append(f"References actual module path: {module_path}")
    else:
        result.failed.append(f"Missing module path reference: {module_path}")

    # Check that exports appear in examples, how-to, or critical patterns sections
    exports = module.get("exports", [])
    if exports:
        examples_section = re.search(r"## Examples(.*?)(?=##|\Z)", output, re.DOTALL)
        examples_text = examples_section.group(1) if examples_section else ""
        howto_section = re.search(r"## How to apply it(.*?)(?=##|\Z)", output, re.DOTALL)
        howto_text = howto_section.group(1) if howto_section else ""
        patterns_section = re.search(r"## Critical Patterns(.*?)(?=\n## [A-Z]|\Z)", output, re.DOTALL)
        patterns_text = patterns_section.group(1) if patterns_section else ""
        combined = examples_text + howto_text + patterns_text

        exports_found = [e for e in exports[:6] if e in combined]
        if len(exports_found) >= min(2, len(exports)):
            result.passed.append(f"Examples use real exports: {exports_found}")
        else:
            result.failed.append(
                f"Examples don't use actual exports. "
                f"Expected some of: {exports[:5]}. Found: {exports_found}"
            )

    # Check for code blocks (examples should have code)
    code_blocks = re.findall(r"```", output)
    if len(code_blocks) >= 2:  # at least one code block (open+close)
        result.passed.append(f"Has {len(code_blocks)//2} code block(s)")
    else:
        result.failed.append("No code blocks in examples")

    # Check imports are referenced
    imports = module.get("imports", [])
    if imports:
        imports_found = [i for i in imports[:5] if i in output]
        if imports_found:
            result.passed.append(f"References actual dependencies: {imports_found}")

    passed = len(result.passed)
    total = passed + len(result.failed)
    result.score = passed / total if total > 0 else 0.0
    return result


def score_pattern_detection(output: str, module: dict, repo_map: dict) -> ScoreResult:
    """
    Conventions / pitfalls section should reflect patterns inferred from the tech stack.
    """
    result = ScoreResult(dimension="pattern_detection")

    tech_stack = repo_map.get("tech_stack", [])

    # Check tech stack is acknowledged
    tech_mentions = sum(1 for t in tech_stack if t.lower() in output.lower())
    if tech_mentions >= min(2, len(tech_stack)):
        result.passed.append(f"Mentions tech stack ({tech_mentions}/{len(tech_stack)} techs)")
    else:
        result.failed.append(f"Doesn't mention tech stack. Expected: {tech_stack}")

    # Check pitfalls/anti-patterns section exists and is non-trivial
    pitfalls = re.search(r"## (?:Pitfalls|Anti-Patterns)(.*?)(?=##|\Z)", output, re.DOTALL)
    if pitfalls:
        pitfalls_text = pitfalls.group(1).strip()
        if len(pitfalls_text) > 100:
            result.passed.append("Pitfalls/Anti-Patterns section is substantive")
        else:
            result.failed.append("Pitfalls/Anti-Patterns section is too brief (<100 chars)")
    else:
        result.failed.append("No Pitfalls or Anti-Patterns section")

    # Check conventions or patterns section
    conventions = re.search(r"## (Conventions|Patterns|Notes)(.*?)(?=##|\Z)", output, re.DOTALL)
    if conventions:
        result.passed.append("Has conventions/patterns section")

    # For FastAPI: should mention dependency injection, router prefix, etc.
    if "FastAPI" in tech_stack:
        fastapi_patterns = ["router", "depend", "prefix", "response_model", "status_code"]
        found = [p for p in fastapi_patterns if p.lower() in output.lower()]
        if found:
            result.passed.append(f"References FastAPI patterns: {found}")
        else:
            result.failed.append("Missing FastAPI-specific patterns")

    # For Next.js: should mention server/client components, metadata, etc.
    if "Next.js" in tech_stack:
        next_patterns = ["server component", "client component", "use client", "metadata", "layout"]
        found = [p for p in next_patterns if p.lower() in output.lower()]
        if found:
            result.passed.append(f"References Next.js patterns: {found}")
        else:
            result.failed.append("Missing Next.js-specific patterns")

    passed = len(result.passed)
    total = passed + len(result.failed)
    result.score = passed / total if total > 0 else 0.0
    return result


def score_multilang_coverage(output: str, layer: dict) -> ScoreResult:
    """
    For layers with multiple languages, the skill should cover all of them.
    """
    result = ScoreResult(dimension="multilang_coverage")

    languages = set()
    for m in layer.get("modules", []):
        if m.get("language"):
            languages.add(m["language"])

    if len(languages) <= 1:
        result.passed.append(f"Single-language layer ({list(languages)[0] if languages else 'none'})")
        result.score = 1.0
        result.notes = "N/A (single language)"
        return result

    # Multi-language: check each language is mentioned
    for lang in languages:
        if lang.lower() in output.lower():
            result.passed.append(f"Covers {lang}")
        else:
            result.failed.append(f"Missing coverage for {lang}")

    # Check for language-specific sections or notes
    lang_sections = re.findall(r"###?\s+([A-Za-z]+)\s", output)
    multilang_hint_patterns = [
        "both", "typescript and python", "python and typescript",
        "cross-language", "shared between"
    ]
    has_multilang_note = any(p in output.lower() for p in multilang_hint_patterns)
    if has_multilang_note:
        result.passed.append("Explicitly addresses multi-language nature")
    elif len(languages) > 1:
        result.failed.append("Doesn't explicitly address multi-language layer")

    passed = len(result.passed)
    total = passed + len(result.failed)
    result.score = passed / total if total > 0 else 0.0
    return result


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

@dataclass
class EvalResult:
    scenario: str
    prompt_type: str
    scores: list[ScoreResult]

    @property
    def overall(self) -> float:
        return sum(s.score for s in self.scores) / len(self.scores) if self.scores else 0.0

    @property
    def grade(self) -> str:
        o = self.overall
        if o >= 0.85:
            return "✅ PASS"
        if o >= 0.60:
            return "⚠️  WARN"
        return "❌ FAIL"


def run_scenario(scenario_name: str, llm=None, verbose: bool = True) -> EvalResult:
    """
    Run a single eval scenario.

    If llm is None, generates a FAKE output to test the scorer itself.
    Pass a real LLM instance to test actual prompt quality.
    """
    scenario_fn = SCENARIOS.get(scenario_name)
    if not scenario_fn:
        raise ValueError(f"Unknown scenario: {scenario_name}. Available: {list(SCENARIOS)}")

    kind, *args = scenario_fn()
    scores = []

    if kind == "module":
        module, repo_map = args
        layer_name = list(repo_map["layers"].keys())[0]
        system, user = skill_prompt(module, layer_name, repo_map)

        if llm:
            output = llm.complete(user, system=system)
        else:
            output = _fake_skill_output(module)

        scores.append(score_trigger_precision(output, module))
        scores.append(score_code_concreteness(output, module))
        scores.append(score_pattern_detection(output, module, repo_map))
        layer = repo_map["layers"][layer_name]
        scores.append(score_multilang_coverage(output, layer))

        if verbose:
            _print_output(output, scenario_name)

    elif kind == "layer":
        layer_name, layer, repo_map = args
        system, user = layer_skill_prompt(layer_name, layer, repo_map)

        if llm:
            output = llm.complete(user, system=system)
        else:
            output = _fake_layer_output(layer_name, layer)

        # For layers: use a synthetic module representative of the layer
        rep_module = layer["modules"][0] if layer["modules"] else {}
        scores.append(score_trigger_precision(output, rep_module))
        scores.append(score_code_concreteness(output, rep_module))
        scores.append(score_pattern_detection(output, rep_module, repo_map))
        scores.append(score_multilang_coverage(output, layer))

        if verbose:
            _print_output(output, scenario_name)

    return EvalResult(scenario=scenario_name, prompt_type=kind, scores=scores)


def run_all(llm=None, verbose: bool = False) -> list[EvalResult]:
    results = []
    for name in SCENARIOS:
        r = run_scenario(name, llm=llm, verbose=verbose)
        results.append(r)
    return results


def print_report(results: list[EvalResult]):
    print("\n" + "="*60)
    print("  RepoForge Prompt Eval Report")
    print("="*60)

    for r in results:
        print(f"\n📋 {r.scenario} ({r.prompt_type})")
        print(f"   Overall: {r.grade}  ({r.overall:.0%})")
        for s in r.scores:
            bar = "█" * int(s.score * 10) + "░" * (10 - int(s.score * 10))
            print(f"   {s.grade} {s.dimension:<25} [{bar}] {s.score:.0%}")
            if s.notes:
                print(f"      note: {s.notes}")
            for p in s.passed:
                print(f"      ✓ {p}")
            for f in s.failed:
                print(f"      ✗ {f}")

    overall_avg = sum(r.overall for r in results) / len(results) if results else 0
    print(f"\n{'='*60}")
    print(f"  Average across all scenarios: {overall_avg:.0%}")
    print("="*60 + "\n")


# ---------------------------------------------------------------------------
# Fake outputs for scorer testing (no LLM needed)
# ---------------------------------------------------------------------------

def _fake_skill_output(module: dict) -> str:
    """Minimal fake that should score reasonably well — used for harness validation."""
    path = module["path"]
    exports = module.get("exports", [])
    imports = module.get("imports", [])
    name = path.replace("/", "_").replace(".", "_")

    return f"""---
name: {name}
description: Manage {module.get('summary_hint', 'module operations')} in this codebase.
triggers:
  - adding a new {exports[0] if exports else 'endpoint'} to {path}
  - modifying {exports[1] if len(exports) > 1 else 'the module'} behavior
  - debugging issues in {module['name']} layer
location: {path}
---

## What this skill does

This skill covers working with `{path}`. It exports `{', '.join(exports[:3])}`.
Uses `{', '.join(imports[:3])}` as dependencies.

## When to use it

- When adding a new function to `{path}`
- When modifying `{exports[0] if exports else 'the module'}`
- When the task involves `{imports[0] if imports else 'this module'}`

## Key files

- `{path}` - main module
- `{'/'.join(path.split('/')[:-1])}/` - layer directory

## How to apply it

1. Open `{path}`
2. Add your function following the existing `{exports[0] if exports else 'pattern'}` pattern
3. Import required deps: `{imports[0] if imports else 'none'}`
4. Run tests

## Examples

```python
from {'.'.join(path.replace('.py','').split('/'))} import {exports[0] if exports else 'module'}

result = {exports[0] if exports else 'function'}()
```

## Pitfalls

- Don't bypass the existing `{exports[0] if exports else 'interface'}` abstraction
- Always handle errors from `{imports[0] if imports else 'dependencies'}`
- Keep functions focused on a single responsibility
"""


def _fake_layer_output(layer_name: str, layer: dict) -> str:
    langs = list(set(m["language"] for m in layer["modules"]))
    modules_text = "\n".join(
        f"- `{m['path']}` — {m.get('summary_hint', m['name'])}"
        for m in layer["modules"]
    )
    return f"""---
name: {layer_name}_layer
description: Work within the {layer_name} layer of this project.
triggers:
  - working on {layer_name} code
  - adding a new module to {layer['path']}
  - modifying shared {', '.join(langs)} code
location: {layer['path']}
---

## Layer overview

The {layer_name} layer lives in `{layer['path']}`. It contains both {' and '.join(langs)} code.
This layer is used across multiple parts of the project.

## Key modules

{modules_text}

## Conventions

- TypeScript types are defined in `types.ts`
- Python validators use pydantic
- Both TypeScript and Python code follow the same domain model

## How to add a new feature

1. Add TypeScript types to `types.ts`
2. Add Python validators to `validators.py`
3. Export from both

## Cross-layer dependencies

Used by both frontend and backend layers.

## Common tasks

- Add a new shared type: edit `types.ts`
- Add a validator: edit `validators.py`
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_output(output: str, label: str):
    print(f"\n{'─'*60}")
    print(f"  Generated output: {label}")
    print('─'*60)
    # Print first 40 lines only
    lines = output.split("\n")
    print("\n".join(lines[:40]))
    if len(lines) > 40:
        print(f"  ... ({len(lines) - 40} more lines)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RepoForge prompt evaluator")
    parser.add_argument("--scenario", default=None, help="Run a specific scenario")
    parser.add_argument("--model", default=None, help="LLM model to use (default: dry-run with fake output)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    llm = None
    if args.model:
        from repoforge.llm import build_llm
        llm = build_llm(model=args.model)
        print(f"🤖 Using model: {llm.model}")
    else:
        print("ℹ️  Dry-run mode (no LLM). Pass --model to test with a real LLM.\n")

    if args.scenario:
        result = run_scenario(args.scenario, llm=llm, verbose=args.verbose or True)
        print_report([result])
    else:
        results = run_all(llm=llm, verbose=args.verbose)
        print_report(results)
