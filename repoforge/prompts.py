"""
prompts.py - Prompt templates for SKILL.md and AGENT.md generation.

Format target: Gentleman-Skills spec (https://github.com/Gentleman-Programming/Gentleman-Skills)
  - YAML frontmatter with: name, description (+ "Trigger:"), license, metadata
  - Content is IMPERATIVE and CONCISE — patterns + code, no verbose explanations
  - The AI reads these skills while coding — every word must earn its place

Agent format: agent-teams-lite compatible (https://github.com/Gentleman-Programming/agent-teams-lite)
  - Delegate-only orchestrator pattern
  - Sub-agents read skill-registry before every task
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Shared system base
# ---------------------------------------------------------------------------

_BASE_SYSTEM = """\
Output ONLY the file content. No preamble, no explanation, no markdown wrapper.
Start directly with the YAML frontmatter (---).
Be CONCISE — the AI reads this while coding. Every line must add value.
Use actual names from the module info provided (real exports, real paths).
"""


# ===========================================================================
# SKILL.md
# ===========================================================================

SKILL_SYSTEM = _BASE_SYSTEM + """\

You are generating a SKILL.md for the Gentleman-Skills / Claude Code ecosystem.

FORMAT (mandatory — do not deviate):

---
name: <kebab-case-name>
description: >
  <One sentence: what patterns this skill covers.>
  Trigger: <When to load — use domain nouns from the module, not generic words>.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Critical Patterns

### <Pattern name>

<One sentence explaining the rule.>

```<language>
// Real code using actual exported names from this module
```

### <Pattern name>

<One sentence.>

```<language>
// Example
```

## When to Use

- <Specific scenario using module/domain nouns>
- <Another scenario — different verb>
- <Debug/fix scenario>

## Commands

```bash
<Relevant commands for this tech stack>
```

## Anti-Patterns

### Don't: <anti-pattern name>

<Why it's wrong — one sentence.>

```<language>
// BAD
```

## Quick Reference

| Task | Pattern |
|------|---------|
| <task> | `<code>` |

RULES:
1. `name` must be kebab-case, action-oriented: `add-fastapi-endpoint`, `extend-user-model`
2. `description` block must contain "Trigger:" on the second line
3. Critical Patterns must use REAL exported names from the module info
4. No sections like "What this skill does" or "Overview" — go straight to patterns
5. Commands section must have real commands for the detected tech stack
6. Minimum 2 Critical Patterns, minimum 1 Anti-Pattern
"""

# Detail-level instructions appended to user prompts
_DETAIL_INSTRUCTIONS = {
    "detailed": (
        "\n\n## Detail level: DETAILED\n"
        "- Include 3+ Critical Patterns with full explanations and longer code examples\n"
        "- Include 2+ Anti-Patterns with before/after code\n"
        "- Include usage examples for every exported function\n"
        "- Quick Reference table should have 5+ rows\n"
    ),
    "standard": "",  # default — no extra instructions
    "concise": (
        "\n\n## Detail level: CONCISE\n"
        "- Keep to 2 Critical Patterns only — the most important ones\n"
        "- Keep to 1 Anti-Pattern — the most dangerous mistake\n"
        "- Code examples should be minimal (3-5 lines each)\n"
        "- Quick Reference table: 3 rows max\n"
        "- Total output under 80 lines\n"
    ),
}


def skill_prompt(module: dict, layer_name: str, repo_map: dict,
                 prompt_detail: str = "standard") -> tuple[str, str]:
    """Build prompt for a module-level SKILL.md.

    Args:
        prompt_detail: "detailed" | "standard" | "concise" — adjusts verbosity.
    """
    tech = ", ".join(repo_map.get("tech_stack", []))
    exports = module.get("exports", [])
    imports = module.get("imports", [])
    exports_str = ", ".join(f"`{e}`" for e in exports[:10]) or "none detected"
    imports_str = ", ".join(f"`{i}`" for i in imports[:8]) or "none"

    layer = repo_map["layers"].get(layer_name, {})
    siblings = [
        m for m in layer.get("modules", [])
        if m["path"] != module["path"]
    ][:4]
    siblings_text = "\n".join(
        f"  - `{m['path']}` (exports: {', '.join(m['exports'][:3])})"
        for m in siblings
        if m.get("exports")
    ) or "  (none)"

    lang_hint = {
        "Python": "python", "TypeScript": "typescript",
        "JavaScript": "javascript", "Go": "go", "Rust": "rust",
        "Java": "java", "Kotlin": "kotlin", "Ruby": "ruby",
        "C#": "csharp", "PHP": "php", "Swift": "swift",
    }.get(module.get("language", ""), "text")

    detail_suffix = _DETAIL_INSTRUCTIONS.get(prompt_detail, "")

    user = f"""Generate a SKILL.md for this module.

## Module
- File: `{module['path']}`
- Language: {module.get('language', 'unknown')}
- Layer: {layer_name}
- Summary: {module.get('summary_hint') or 'not available'}
- Exports: {exports_str}
- Uses: {imports_str}

## Sibling modules (for context)
{siblings_text}

## Project
- Stack: {tech}
- Entry points: {", ".join(repo_map.get("entry_points", [])) or "none"}

## Requirements
- `name` field: kebab-case action verb + domain noun from THIS module.
  Good: `add-{module['name'].lower().replace('_','-')}-endpoint`, `extend-{module['name'].lower().replace('_','-')}-model`
  Bad: `{module['name'].lower()}-module`, `use-{module['name'].lower()}`
- Critical Patterns MUST use these real exports: {exports_str}
- Code blocks MUST use `{lang_hint}` language tag
- Commands must be real {tech} commands (not placeholders)
- Trigger in description must mention: `{module['name']}` or its domain
{detail_suffix}"""
    return SKILL_SYSTEM, user


# ---------------------------------------------------------------------------
# Layer-level SKILL.md (covers the whole layer)
# ---------------------------------------------------------------------------

LAYER_SKILL_SYSTEM = _BASE_SYSTEM + """\

You are generating a layer-level SKILL.md for the Gentleman-Skills ecosystem.
This skill covers an entire layer/package of a project, not a single module.

FORMAT (mandatory):

---
name: <layer-name>-layer
description: >
  <What this layer owns and its role in the project.>
  Trigger: When working in <layer-name>/ — adding, modifying, or debugging <domain>.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Layer Structure

```
<layer-path>/
├── <key file> — <what it does>
├── <key file> — <what it does>
└── <key file> — <what it does>
```

## Critical Patterns

### <Pattern 1 — most important convention in this layer>

<One sentence rule.>

```<language>
// Example using real exported names
```

### <Pattern 2>

```<language>
// Example
```

## When to Use

- <Task specific to this layer with domain nouns>
- <Another task>
- <Cross-layer integration scenario>

## Adding a New <Entity/Feature/Component>

1. <Step 1 with real file path>
2. <Step 2>
3. <Step 3>
4. <Verification step>

## Commands

```bash
<Real commands to run/test/build this layer>
```

## Anti-Patterns

- **Don't**: <layer-specific mistake> — <why>
- **Don't**: <cross-layer mistake> — <why>

## Quick Reference

| Task | File | Pattern |
|------|------|---------|
| <common task> | `<path>` | `<code>` |

RULES:
1. If multiple languages in layer — include one code block per language
2. "Adding a New X" section is mandatory — use the most common task for this layer type
3. Anti-patterns must be layer-specific, not generic
4. Quick Reference must have real file paths
"""


def layer_skill_prompt(layer_name: str, layer: dict, repo_map: dict,
                      prompt_detail: str = "standard") -> tuple[str, str]:
    """Build prompt for a layer-level SKILL.md.

    Args:
        prompt_detail: "detailed" | "standard" | "concise" — adjusts verbosity.
    """
    tech = ", ".join(repo_map.get("tech_stack", []))
    modules = layer.get("modules", [])

    by_lang: dict[str, list] = {}
    for m in modules[:20]:
        lang = m.get("language", "Unknown")
        by_lang.setdefault(lang, []).append(m)

    modules_text = ""
    for lang, lang_modules in by_lang.items():
        modules_text += f"\n  [{lang}]\n"
        for m in lang_modules[:8]:
            exports_preview = ", ".join(m.get("exports", [])[:4])
            hint = m.get("summary_hint", "")[:60]
            modules_text += (
                f"    - `{m['path']}`"
                + (f" — {hint}" if hint else "")
                + (f" | exports: {exports_preview}" if exports_preview else "")
                + "\n"
            )

    other_layers = [k for k in repo_map["layers"] if k != layer_name]
    languages = list(by_lang.keys())
    is_multilang = len(languages) > 1

    detail_suffix = _DETAIL_INSTRUCTIONS.get(prompt_detail, "")

    user = f"""Generate a layer-level SKILL.md for the **"{layer_name}"** layer.

## Layer
- Path: `{layer['path']}`
- Languages: {", ".join(languages)}
- Modules: {len(modules)} files
- Other layers: {", ".join(other_layers) or "none"}

## Modules
{modules_text.strip() or "  (no modules detected)"}

## Project
- Stack: {tech}
- Config files: {", ".join(repo_map.get("config_files", [])) or "none"}

## Requirements
- `name` must be: `{layer_name}-layer`
- Trigger must mention: `{layer_name}/` directory and its main responsibility
{"- MULTILANGUAGE LAYER: include one code block per language: " + ", ".join(languages) if is_multilang else "- Single language: " + (languages[0] if languages else "unknown")}
- 'Adding a New X' step names must match real file structure shown above
- Anti-patterns must cover cross-layer issues (what breaks when {layer_name} changes)
{detail_suffix}"""
    return LAYER_SKILL_SYSTEM, user


# ===========================================================================
# AGENT.md — agent-teams-lite compatible
# ===========================================================================

AGENT_SYSTEM = _BASE_SYSTEM + """\

You are generating an AGENT.md compatible with agent-teams-lite and Claude Code.

An agent is a SPECIALIZED sub-agent. It NEVER does work outside its domain.
The orchestrator delegates to it. It reads the skill-registry before every task.

FORMAT (mandatory):

---
name: <agent-name>
description: >
  Specialized agent for <domain>. Handles <specific responsibilities>.
  Trigger: When the orchestrator needs to <action> in <layer/domain>.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Role

<2-3 sentences: what this agent owns, what it never touches.>

## Capabilities

- <Specific capability 1 with domain noun>
- <Specific capability 2>
- <Specific capability 3>

## Workflow

Before starting ANY task:
1. Read `.atl/skill-registry.md` to discover available skills
2. Load relevant skills from the registry
3. Execute the task following the loaded skill patterns

Task execution:
1. <Domain-specific step 1>
2. <Domain-specific step 2>
3. <Verification step>
4. Report back to orchestrator with: files changed, tests status, blockers

## Skills to Load

- `<path/to/SKILL.md>` — <when to load it>
- `<path/to/SKILL.md>` — <when to load it>

## Constraints

- ONLY modify files inside `<layer-path>/`
- NEVER modify: <other layers>
- ALWAYS run tests before reporting done
- NEVER push to remote — report back to orchestrator

## Input

```
task: <what to do>
context: <relevant info>
skills_needed: [<skill1>, <skill2>]
```

## Output

```
status: done | blocked | partial
files_changed: [<list>]
tests: passed | failed | skipped
summary: <one paragraph>
blockers: <if any>
```

RULES:
1. `name` must be: `<layer>-agent` (e.g. `frontend-agent`, `backend-agent`)
2. Workflow MUST start with reading skill-registry — this is non-negotiable
3. "Skills to Load" MUST contain ONLY the exact paths provided in the prompt — no invented paths
4. Capabilities MUST be derived ONLY from the actual modules listed — no invention
5. Constraints must name real layer paths from the prompt
6. Input/Output must match the actual tech stack (Python, TypeScript, etc. — not generic)
7. NEVER invent module names, file paths, or skill paths not explicitly given
"""


def agent_prompt(layer_name: str, layer: dict, repo_map: dict,
                 all_layers: list[str],
                 generated_skills: list[str] | None = None) -> tuple[str, str]:
    """Build prompt for a layer AGENT.md.

    generated_skills: list of SKILL.md absolute paths already written for this layer.
    Passing them avoids the LLM inventing skill paths that don't exist.
    """
    tech = ", ".join(repo_map.get("tech_stack", []))
    other_agents = [f"`{layer}-agent`" for layer in all_layers if layer != layer_name]

    # Key modules for this layer
    modules_hint = "\n".join(
        f"  - `{m['path']}`" + (f" — {m.get('summary_hint','')[:60]}" if m.get('summary_hint') else "")
        for m in layer.get("modules", [])[:8]
    ) or "  (none)"

    # Real generated skill paths for this layer (relative display)
    if generated_skills:
        skills_hint = "\n".join(
            f"  - `{p}` — load when working with {Path(p).parent.name}"
            for p in generated_skills
            if "SKILL.md" in p
        )
    else:
        skills_dir = f".claude/skills/{layer_name}/"
        skills_hint = f"  - `{skills_dir}SKILL.md` — layer-level patterns"

    user = f"""Generate an AGENT.md for the **"{layer_name}"** agent.

## Layer
- Name: {layer_name}
- Path: `{layer['path']}`
- Stack: {tech}

## Key modules (ONLY reference these — do NOT invent others)
{modules_hint}

## Real generated skills (use EXACTLY these paths in "Skills to Load")
{skills_hint}

## Project structure
- All layers: {", ".join(all_layers)}
- Sibling agents: {", ".join(other_agents) or "none"}

## Requirements
- `name` must be: `{layer_name}-agent`
- Capabilities must describe ONLY what the modules above actually do
- "Skills to Load" MUST list ONLY the exact paths shown in "Real generated skills"
- Constraints: "ONLY modify files inside `{layer['path']}/`"
- Workflow step 1 MUST be: Read `.atl/skill-registry.md`
- Do NOT invent skill paths, capabilities, or module names not shown above
"""
    return AGENT_SYSTEM, user


# ---------------------------------------------------------------------------
# Orchestrator AGENT.md — delegate-only pattern
# ---------------------------------------------------------------------------

ORCHESTRATOR_SYSTEM = _BASE_SYSTEM + """\

You are generating the orchestrator AGENT.md for agent-teams-lite / Claude Code.

The orchestrator is DELEGATE-ONLY. It NEVER writes code or modifies files directly.
Every real task is delegated to a specialized sub-agent.
It reads the skill-registry, routes tasks, and assembles results.

FORMAT (mandatory):

---
name: orchestrator
description: >
  Delegate-only orchestrator for <project>. Routes tasks to specialized agents.
  Trigger: Any task that spans multiple layers or needs coordination.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Role

Lightweight coordinator. Receives tasks, delegates 100% of implementation to sub-agents.
NEVER writes code. NEVER modifies files. Only reads, plans, delegates, and synthesizes.

## Startup Protocol

Before handling any task:
1. Read `.atl/skill-registry.md` — understand available skills and conventions
2. Identify which layer(s) the task touches
3. Select the appropriate sub-agent(s)
4. Delegate with full context

## Routing Table

| Task type | Delegate to |
|-----------|-------------|
<routing rows based on layers>

## Delegation Protocol

```
1. Receive task from user
2. Read skill-registry (if not already loaded)
3. Decompose into sub-tasks per layer
4. For each sub-task:
   - Launch sub-agent with: task + context + relevant skills
   - Wait for result
5. Synthesize results
6. Report back to user
```

## Sub-agents

<list of all layer agents with one-line descriptions>

## For Complex Features (SDD mode)

When the task is substantial (new feature, refactor, multi-layer change):
1. Launch EXPLORER sub-agent → codebase analysis
2. Show summary, get approval
3. Launch PROPOSER → proposal
4. Launch SPEC WRITER → spec
5. Launch IMPLEMENTER (per layer) → code
6. Launch VERIFIER → validation

## Constraints

- NEVER write code or modify files directly
- NEVER skip the skill-registry read
- ALWAYS get user approval before multi-file changes
- ALWAYS report sub-agent results back to user

RULES:
1. Routing Table must have one row per layer
2. Sub-agents list must match the generated layer agents exactly
3. The "NEVER writes code" constraint is non-negotiable — enforce it in the content
"""


def orchestrator_prompt(repo_map: dict) -> tuple[str, str]:
    """Build prompt for the orchestrator AGENT.md."""
    tech = ", ".join(repo_map.get("tech_stack", []))
    layers = list(repo_map["layers"].keys())

    layer_details = "\n".join(
        f"  - `{name}-agent` — handles `{data['path']}/` "
        f"({len(data.get('modules', []))} modules, "
        f"{', '.join(list(set(m.get('language','') for m in data.get('modules',[])))[:2])})"
        for name, data in repo_map["layers"].items()
    )

    routing_rows = "\n".join(
        f"| Work in `{data['path']}/` | `{name}-agent` |"
        for name, data in repo_map["layers"].items()
    )

    user = f"""Generate an orchestrator AGENT.md for this project.

## Project
- Name: {repo_map.get('root', '.').split('/')[-1]}
- Stack: {tech}
- Layers: {", ".join(layers)}
- Entry points: {", ".join(repo_map.get("entry_points", [])) or "none"}

## Layer agents available
{layer_details}

## Routing hints (use these for the Routing Table)
{routing_rows}

## Requirements
- `name` must be: `orchestrator`
- Routing Table must have one row per layer shown above
- Sub-agents list must name: {", ".join(f"`{layer}-agent`" for layer in layers)}
- Enforce "NEVER writes code" in Constraints — this is the core pattern
- For single-layer project: simplify to "delegates all tasks to `{layers[0]}-agent`"
"""
    return ORCHESTRATOR_SYSTEM, user


# ===========================================================================
# Skill Registry — agent-teams-lite compatible
# (.atl/skill-registry.md)
# ===========================================================================

def build_skill_registry(
    generated_skills: list[str],
    repo_map: dict,
    output_root: Path,
    project_root: Path,
) -> str:
    """
    Generate .atl/skill-registry.md content deterministically (no LLM needed).

    Format matches agent-teams-lite skill-registry spec:
    - Skills table: Trigger | Skill | Path (all paths relative to project_root)
    - Project Conventions table: File | Path | Notes

    Handles the case where output_root is outside project_root (e.g. /tmp/).
    """
    from pathlib import Path as _Path

    def _safe_rel(p: _Path, base: _Path) -> str:
        """Return relative path string, or absolute if outside base."""
        try:
            return str(p.resolve().relative_to(base.resolve()))
        except ValueError:
            return str(p)

    lines = [
        "# Skill Registry\n\n",
        "As your FIRST step before starting any work, identify and load skills "
        "relevant to your task from this registry.\n\n",
    ]

    # --- Skills table
    lines.append("## Skills\n\n")
    lines.append("| Trigger | Skill | Path |\n")
    lines.append("|---------|-------|------|\n")

    for skill_path_str in generated_skills:
        skill_path = _Path(skill_path_str).resolve()
        if skill_path.name != "SKILL.md":
            continue

        # Always use path relative to output_root to parse structure,
        # but display relative to project_root when possible.
        try:
            rel_to_out = skill_path.relative_to(output_root.resolve())
        except ValueError:
            # Skill is outside output_root — use full path parts
            rel_to_out = skill_path

        # Parse structure: <anything>/skills/<layer>/[<module>/]SKILL.md
        parts = rel_to_out.parts
        # Find "skills" segment
        try:
            skills_idx = next(i for i, p in enumerate(parts) if p == "skills")
            layer = parts[skills_idx + 1] if skills_idx + 1 < len(parts) else "main"
            # Module level: skills/<layer>/<module>/SKILL.md  → len after skills = 3
            after_skills = parts[skills_idx + 1:]  # e.g. ("backend", "users", "SKILL.md")
            if len(after_skills) == 3:  # layer / module / SKILL.md
                module = after_skills[1]
                skill_name = module
                trigger = f"Working with `{module}` in `{layer}/`"
            else:  # layer / SKILL.md
                skill_name = f"{layer}-layer"
                trigger = f"Working in `{layer}/` — adding, modifying, or debugging {layer} code"
        except StopIteration:
            # No "skills" segment found — fallback
            skill_name = skill_path.parent.name
            trigger = f"Working with `{skill_name}`"

        display_path = _safe_rel(skill_path, project_root)
        lines.append(f"| {trigger} | `{skill_name}` | `{display_path}` |\n")

    # --- Project Conventions table
    lines.append("\n## Project Conventions\n\n")
    lines.append("| File | Path | Notes |\n")
    lines.append("|------|------|-------|\n")

    convention_files = [
        ("AGENTS.md",    project_root / "AGENTS.md",    "Agent instructions"),
        ("CLAUDE.md",    project_root / "CLAUDE.md",    "Claude Code instructions"),
        (".cursorrules", project_root / ".cursorrules",  "Cursor rules"),
        ("GEMINI.md",    project_root / "GEMINI.md",    "Gemini CLI instructions"),
        ("COPILOT.md",   project_root / "COPILOT.md",   "GitHub Copilot instructions"),
    ]
    found_any = False
    for fname, fpath, note in convention_files:
        if fpath.exists():
            found_any = True
            lines.append(f"| `{fname}` | `{_safe_rel(fpath, project_root)}` | {note} |\n")
    if not found_any:
        lines.append("| — | — | No convention files found |\n")

    # --- Project Context
    lines.append("\n## Project Context\n\n")
    lines.append(f"- **Tech stack**: {', '.join(repo_map.get('tech_stack', ['unknown']))}\n")
    layers = repo_map.get('layers', {})
    lines.append(f"- **Layers**: {', '.join(layers.keys())}\n")
    entry_points = repo_map.get('entry_points', [])
    lines.append(f"- **Entry points**: {', '.join(entry_points) or 'none'}\n")
    lines.append("- **Generated by**: repoforge\n")

    return "".join(lines)


