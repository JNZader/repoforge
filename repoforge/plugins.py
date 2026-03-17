"""
plugins.py - Plugin packaging for generated skills — Skills > Commands > Plugins hierarchy.

Inspired by:
  - pm-skills (Skills > Commands > Plugins organizational model)
  - anthropics/knowledge-work-plugins (plugin.json manifest + commands/ + skills/)
  - Generative-Media-Skills (Core/Library architecture split)

Hierarchy:
  Skills   = Knowledge/patterns (SKILL.md files)
  Commands = Executable workflows that chain multiple skills
  Plugin   = Composable package with manifest, skills, commands, and metadata

All functions are deterministic (no LLM) except commands_prompt() which
produces a prompt for the LLM to fill in detailed workflow steps.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Command:
    """An executable workflow that chains multiple skills."""
    name: str              # e.g. "create-endpoint"
    description: str       # What this command does
    skills_used: list[str] # Which skills this command requires
    steps: list[str]       # Ordered steps to execute
    preconditions: list[str] = field(default_factory=list)
    verification: str = ""  # How to verify it worked


@dataclass
class PluginManifest:
    """A composable plugin package with manifest, skills, commands, and metadata."""
    name: str              # e.g. "fastapi-backend"
    version: str           # "1.0.0"
    description: str
    author: str = "RepoForge"
    skills: list[str] = field(default_factory=list)      # paths to SKILL.md files
    commands: list[Command] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)       # paths to AGENT.md files
    hooks: list[str] = field(default_factory=list)        # paths to HOOKS.md files
    triggers: list[str] = field(default_factory=list)     # when to activate this plugin
    dependencies: list[str] = field(default_factory=list) # other plugins needed


# ---------------------------------------------------------------------------
# Command detection patterns — maps tech stack / layer patterns to commands
# ---------------------------------------------------------------------------

# (pattern_key, command_name, description, preconditions, verification)
_BACKEND_COMMANDS = [
    (
        {"layers": ["backend"], "tech_any": ["FastAPI", "Django", "Flask", "Express", "Fastify", "Go", "Rust", "Java"]},
        "add-endpoint",
        "Add a new API endpoint with route, handler, and validation",
        ["Backend layer exists", "Router/controller structure in place"],
        "Run API tests and verify endpoint responds",
    ),
    (
        {"layers": ["backend"], "modules_any": ["model", "models", "schema", "schemas", "db", "database"]},
        "add-model",
        "Add a new data model/schema with migrations and validation",
        ["Database or ORM configured", "Models directory exists"],
        "Run migrations and verify model creation",
    ),
    (
        {"layers": ["backend"], "modules_any": ["service", "services", "repository", "repositories"]},
        "add-service",
        "Add a new business logic service with dependency injection",
        ["Service layer exists"],
        "Run unit tests for the new service",
    ),
    (
        {"layers": ["backend"], "modules_any": ["middleware", "interceptor"]},
        "add-middleware",
        "Add a new middleware/interceptor to the request pipeline",
        ["Backend framework configured"],
        "Verify middleware is registered and executes in order",
    ),
]

_FRONTEND_COMMANDS = [
    (
        {"layers": ["frontend"], "tech_any": ["React", "Vue", "Svelte", "Next.js"]},
        "add-component",
        "Add a new UI component with props, styles, and tests",
        ["Frontend framework configured", "Component directory exists"],
        "Run component tests and verify rendering",
    ),
    (
        {"layers": ["frontend"], "modules_any": ["store", "stores", "context", "provider"]},
        "add-store",
        "Add a new state management store/slice",
        ["State management library configured"],
        "Verify store initializes and state updates work",
    ),
    (
        {"layers": ["frontend"], "modules_any": ["hooks", "composables"]},
        "add-hook",
        "Add a new custom hook/composable with tests",
        ["Frontend framework configured"],
        "Run hook tests and verify in component integration",
    ),
]

_TEST_COMMANDS = [
    (
        {"has_tests": True},
        "add-test",
        "Add tests for an existing module following project test patterns",
        ["Test framework configured", "Target module exists"],
        "Run test suite and verify all tests pass",
    ),
]

_INFRA_COMMANDS = [
    (
        {"tech_any": ["Docker"]},
        "add-service",
        "Add a new Docker service to docker-compose with health checks",
        ["docker-compose.yml exists"],
        "Run docker-compose up and verify service health",
    ),
]

_ALL_COMMAND_PATTERNS = _BACKEND_COMMANDS + _FRONTEND_COMMANDS + _TEST_COMMANDS + _INFRA_COMMANDS


# ---------------------------------------------------------------------------
# Deterministic command builder
# ---------------------------------------------------------------------------

def build_commands(repo_map: dict, skills: dict[str, str], complexity: dict) -> list[Command]:
    """Deterministically generate commands based on detected patterns.

    Commands are generated based on tech stack and layer analysis — no LLM needed.
    Each command references the skills it would use and provides basic step outlines.

    Args:
        repo_map: Output from scan_repo().
        skills: Dict of {relative_path: content} for generated skills.
        complexity: Output from classify_complexity().

    Returns:
        List of Command objects for the detected tech stack.
    """
    tech_stack = set(repo_map.get("tech_stack", []))
    layers = set(repo_map.get("layers", {}).keys())
    all_modules = set()
    has_tests = False

    for layer_data in repo_map.get("layers", {}).values():
        for mod in layer_data.get("modules", []):
            all_modules.add(mod.get("name", ""))
            # Also add directory names from path for broader matching
            # e.g. "src/hooks/useAuth.ts" → adds "hooks"
            for part in Path(mod.get("path", "")).parts:
                stem = Path(part).stem.lower()
                if stem and stem not in ("src", ".", ""):
                    all_modules.add(stem)
            if "test" in mod.get("path", "").lower():
                has_tests = True

    # Collect skill paths for referencing
    skill_paths = list(skills.keys()) if skills else []

    commands: list[Command] = []
    seen_names: set[str] = set()

    for pattern, cmd_name, description, preconditions, verification in _ALL_COMMAND_PATTERNS:
        # Skip duplicates (e.g. infra "add-service" vs backend "add-service")
        if cmd_name in seen_names:
            continue

        # Check if pattern matches
        if not _matches_pattern(pattern, tech_stack, layers, all_modules, has_tests):
            continue

        # Determine which skills this command uses
        cmd_skills = _find_related_skills(cmd_name, skill_paths, layers)

        # Build basic steps based on command type
        steps = _build_steps(cmd_name, repo_map)

        commands.append(Command(
            name=cmd_name,
            description=description,
            skills_used=cmd_skills,
            steps=steps,
            preconditions=preconditions,
            verification=verification,
        ))
        seen_names.add(cmd_name)

    return commands


def _matches_pattern(
    pattern: dict,
    tech_stack: set[str],
    layers: set[str],
    modules: set[str],
    has_tests: bool,
) -> bool:
    """Check if a command pattern matches the current project."""
    # Check required layers
    if "layers" in pattern:
        if not any(layer in layers for layer in pattern["layers"]):
            return False

    # Check tech stack (any match)
    if "tech_any" in pattern:
        if not tech_stack & set(pattern["tech_any"]):
            return False

    # Check module names (any match)
    if "modules_any" in pattern:
        if not modules & set(pattern["modules_any"]):
            return False

    # Check test existence
    if "has_tests" in pattern:
        if pattern["has_tests"] != has_tests:
            return False

    return True


def _find_related_skills(
    cmd_name: str,
    skill_paths: list[str],
    layers: set[str],
) -> list[str]:
    """Find skill paths related to a command name."""
    # Map command names to likely layer/module associations
    cmd_to_layer_hints = {
        "add-endpoint": ["backend"],
        "add-model": ["backend"],
        "add-service": ["backend"],
        "add-middleware": ["backend"],
        "add-component": ["frontend"],
        "add-store": ["frontend"],
        "add-hook": ["frontend"],
        "add-test": list(layers),  # tests can apply to any layer
    }
    layer_hints = cmd_to_layer_hints.get(cmd_name, list(layers))

    related: list[str] = []
    for path in skill_paths:
        path_lower = path.lower()
        for hint in layer_hints:
            if hint.lower() in path_lower:
                related.append(path)
                break

    return related[:5]  # cap at 5 skills per command


def _build_steps(cmd_name: str, repo_map: dict) -> list[str]:
    """Build basic step outlines for a command.

    These are deterministic templates — the LLM fills in project-specific details
    when commands_prompt() is used.
    """
    tech = repo_map.get("tech_stack", [])
    tech_str = ", ".join(tech[:3]) if tech else "the project"

    step_templates = {
        "add-endpoint": [
            "Create the route handler file in the appropriate routes/controllers directory",
            "Define request/response schemas or types",
            "Implement the handler logic with proper error handling",
            "Register the route in the router/app configuration",
            "Add input validation and authentication if needed",
            "Write tests for the new endpoint",
        ],
        "add-model": [
            "Define the model/schema in the models directory",
            "Add field types, constraints, and relationships",
            "Create or update database migration",
            "Add model validation rules",
            "Update any dependent services or repositories",
            "Write model tests",
        ],
        "add-service": [
            "Create the service class/module in the services directory",
            "Define the service interface and methods",
            "Implement business logic with proper error handling",
            "Wire up dependencies (repositories, clients, etc.)",
            "Write unit tests with mocked dependencies",
        ],
        "add-middleware": [
            "Create the middleware function/class",
            "Implement request/response interception logic",
            "Register the middleware in the correct order",
            "Add configuration options if needed",
            "Write tests verifying middleware behavior",
        ],
        "add-component": [
            "Create the component file with props interface",
            "Implement the component structure and styling",
            "Add event handlers and state management",
            "Export the component from the appropriate index",
            "Write component tests",
        ],
        "add-store": [
            "Create the store/slice file in the stores directory",
            "Define the state shape and initial values",
            "Implement actions/mutations for state updates",
            "Add selectors/getters for derived state",
            "Write store tests",
        ],
        "add-hook": [
            "Create the hook/composable file",
            "Define the hook signature and return type",
            "Implement the hook logic with proper cleanup",
            "Export from the hooks index",
            "Write hook tests with render testing",
        ],
        "add-test": [
            "Identify the module to test and its public API",
            "Create the test file following existing test patterns",
            "Write test cases covering happy path, edge cases, and errors",
            f"Mock external dependencies as needed for {tech_str}",
            "Run the test suite and verify all tests pass",
        ],
    }

    return step_templates.get(cmd_name, [
        "Identify the target location for the new code",
        "Implement following existing project patterns",
        "Add appropriate tests",
        "Verify everything works",
    ])


# ---------------------------------------------------------------------------
# Plugin manifest builder
# ---------------------------------------------------------------------------

def build_plugin_manifest(
    repo_map: dict,
    generated_files: dict,
    complexity: dict,
) -> PluginManifest:
    """Build a plugin manifest from generated artifacts.

    Analyzes what was generated and organizes it into a plugin structure.

    Args:
        repo_map: Output from scan_repo().
        generated_files: The 'generated' dict from generate_artifacts()
                         containing 'skills', 'agents', 'hooks' etc.
        complexity: Output from classify_complexity().

    Returns:
        PluginManifest with all detected metadata.
    """
    tech = repo_map.get("tech_stack", [])
    layers = list(repo_map.get("layers", {}).keys())

    # Derive plugin name from tech stack + project
    root_name = Path(repo_map.get("root", ".")).name
    primary_tech = tech[0].lower().replace(" ", "-").replace(".", "") if tech else "generic"
    plugin_name = f"{root_name}-{primary_tech}" if root_name != "." else primary_tech

    # Build description from tech stack and layers
    tech_str = ", ".join(tech[:4]) if tech else "mixed"
    layers_str = ", ".join(layers) if layers else "main"
    description = (
        f"AI coding assistant plugin for {root_name}. "
        f"Tech stack: {tech_str}. Layers: {layers_str}."
    )

    # Collect paths from generated files
    skills = generated_files.get("skills", [])
    agents = generated_files.get("agents", [])
    hooks_path = generated_files.get("hooks", "")

    # Build commands from detected patterns
    # We need skill contents for command building — use paths as stand-in
    skill_dict = {p: "" for p in skills}
    commands = build_commands(repo_map, skill_dict, complexity)

    # Triggers: when to activate this plugin
    triggers = [f"Working in {layer}/" for layer in layers]
    if tech:
        triggers.append(f"Using {', '.join(tech[:3])}")

    return PluginManifest(
        name=plugin_name,
        version="1.0.0",
        description=description,
        author="RepoForge",
        skills=skills,
        commands=commands,
        agents=agents,
        hooks=[hooks_path] if hooks_path else [],
        triggers=triggers,
        dependencies=[],
    )


# ---------------------------------------------------------------------------
# LLM prompt for detailed command workflows
# ---------------------------------------------------------------------------

def commands_prompt(repo_map: dict, complexity: dict) -> str:
    """Generate a prompt for the LLM to produce detailed command workflows.

    Uses detected patterns to ask the LLM to fill in project-specific step
    details for each command identified by build_commands().

    Args:
        repo_map: Output from scan_repo().
        complexity: Output from classify_complexity().

    Returns:
        User prompt string (system prompt is the base skill system prompt).
    """
    tech = ", ".join(repo_map.get("tech_stack", []))
    layers = repo_map.get("layers", {})
    entry_points = ", ".join(repo_map.get("entry_points", [])) or "none"
    config_files = ", ".join(repo_map.get("config_files", [])) or "none"

    # Build commands deterministically first
    skill_dict: dict[str, str] = {}
    commands = build_commands(repo_map, skill_dict, complexity)

    if not commands:
        return ""

    # Format commands for the prompt
    commands_text = ""
    for cmd in commands:
        skills_str = ", ".join(f"`{s}`" for s in cmd.skills_used[:3]) or "layer skill"
        steps_str = "\n".join(f"   {i+1}. {step}" for i, step in enumerate(cmd.steps))
        commands_text += f"""
### {cmd.name}
- Description: {cmd.description}
- Skills used: {skills_str}
- Preconditions: {", ".join(cmd.preconditions)}
- Steps:
{steps_str}
- Verification: {cmd.verification}
"""

    # Layer module summaries for context
    modules_text = ""
    for layer_name, layer_data in layers.items():
        modules = layer_data.get("modules", [])[:5]
        if modules:
            mod_list = ", ".join(
                f"`{m['name']}`" for m in modules
            )
            modules_text += f"  - {layer_name}: {mod_list}\n"

    prompt = f"""Generate detailed command workflow documents for this project's plugin.

## Project
- Tech stack: {tech}
- Layers: {", ".join(layers.keys())}
- Entry points: {entry_points}
- Config: {config_files}
- Complexity: {complexity.get('size', 'medium')}

## Key modules
{modules_text.strip() or "  (auto-detected)"}

## Commands to detail
{commands_text}

## Output format

For EACH command above, output a markdown document with this structure:

# <command-name>

> <one-line description>

## Preconditions

- <precondition 1>
- <precondition 2>

## Steps

### 1. <Step name>

<Detailed explanation with actual file paths and code patterns from THIS project.>

```<language>
// Example code using real project patterns
```

### 2. <Step name>

...

## Verification

```bash
<Commands to verify the result>
```

## Related Skills

- `<skill-path>` - <when to reference>

---

RULES:
1. Each step MUST reference real file paths from this project (not generic placeholders)
2. Code examples MUST use the project's actual tech stack ({tech})
3. Commands MUST be real commands for this stack
4. Keep each command document concise — focus on the HOW, not the WHY
5. Output all commands in a single response, separated by `---`
"""
    return prompt


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def manifest_to_json(manifest: PluginManifest) -> str:
    """Serialize manifest to JSON (for plugin.json).

    Compatible with Anthropic's plugin.json format from knowledge-work-plugins.

    Args:
        manifest: PluginManifest to serialize.

    Returns:
        JSON string with 2-space indentation.
    """
    data = {
        "name": manifest.name,
        "version": manifest.version,
        "description": manifest.description,
        "author": manifest.author,
        "skills": manifest.skills,
        "commands": [
            {
                "name": cmd.name,
                "description": cmd.description,
                "skills_used": cmd.skills_used,
                "steps": cmd.steps,
                "preconditions": cmd.preconditions,
                "verification": cmd.verification,
            }
            for cmd in manifest.commands
        ],
        "agents": manifest.agents,
        "hooks": manifest.hooks,
        "triggers": manifest.triggers,
        "dependencies": manifest.dependencies,
    }
    return json.dumps(data, indent=2) + "\n"


def manifest_to_markdown(manifest: PluginManifest) -> str:
    """Serialize manifest to markdown (for PLUGIN.md readme).

    Human-readable version of the plugin manifest.

    Args:
        manifest: PluginManifest to serialize.

    Returns:
        Markdown string.
    """
    lines: list[str] = []

    lines.append(f"# {manifest.name}\n")
    lines.append(f"> {manifest.description}\n")
    lines.append(f"**Version**: {manifest.version}  ")
    lines.append(f"**Author**: {manifest.author}\n")

    # Triggers
    if manifest.triggers:
        lines.append("## Triggers\n")
        for trigger in manifest.triggers:
            lines.append(f"- {trigger}")
        lines.append("")

    # Skills
    if manifest.skills:
        lines.append("## Skills\n")
        for skill in manifest.skills:
            lines.append(f"- `{skill}`")
        lines.append("")

    # Commands
    if manifest.commands:
        lines.append("## Commands\n")
        lines.append("| Command | Description | Skills Used |")
        lines.append("|---------|-------------|-------------|")
        for cmd in manifest.commands:
            skills_str = ", ".join(f"`{s}`" for s in cmd.skills_used[:3]) or "—"
            lines.append(f"| `{cmd.name}` | {cmd.description} | {skills_str} |")
        lines.append("")

        # Command details
        for cmd in manifest.commands:
            lines.append(f"### {cmd.name}\n")
            lines.append(f"{cmd.description}\n")
            if cmd.preconditions:
                lines.append("**Preconditions:**")
                for pre in cmd.preconditions:
                    lines.append(f"- {pre}")
                lines.append("")
            lines.append("**Steps:**")
            for i, step in enumerate(cmd.steps, 1):
                lines.append(f"{i}. {step}")
            lines.append("")
            if cmd.verification:
                lines.append(f"**Verification:** {cmd.verification}\n")

    # Agents
    if manifest.agents:
        lines.append("## Agents\n")
        for agent in manifest.agents:
            lines.append(f"- `{agent}`")
        lines.append("")

    # Hooks
    if manifest.hooks:
        lines.append("## Hooks\n")
        for hook in manifest.hooks:
            lines.append(f"- `{hook}`")
        lines.append("")

    # Dependencies
    if manifest.dependencies:
        lines.append("## Dependencies\n")
        for dep in manifest.dependencies:
            lines.append(f"- `{dep}`")
        lines.append("")

    lines.append("## Installation\n")
    lines.append("This plugin is auto-generated by RepoForge. To install:\n")
    lines.append("1. Copy the `.claude/` directory to your project root")
    lines.append("2. Skills and agents are loaded automatically by Claude Code")
    lines.append("3. Commands in `commands/` provide step-by-step workflows")
    lines.append("4. The `plugin.json` manifest describes the full plugin structure\n")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# File writer
# ---------------------------------------------------------------------------

def write_plugin(
    workspace: str,
    manifest: PluginManifest,
    commands_content: str = "",
) -> dict[str, str]:
    """Write plugin structure to disk.

    Creates:
      .claude/
        plugin.json           <- manifest
        PLUGIN.md             <- human-readable manifest
        commands/
          <command>.md        <- command workflows (if commands_content provided)

    Args:
        workspace: Project root path.
        manifest: PluginManifest to write.
        commands_content: LLM-generated detailed command workflows (optional).

    Returns:
        Dict of {relative_path: content} for all written files.
    """
    root = Path(workspace)
    claude_dir = root / ".claude"
    written: dict[str, str] = {}

    # 1. Write plugin.json
    plugin_json = manifest_to_json(manifest)
    plugin_json_path = claude_dir / "plugin.json"
    plugin_json_path.parent.mkdir(parents=True, exist_ok=True)
    plugin_json_path.write_text(plugin_json, encoding="utf-8")
    written[str(plugin_json_path.relative_to(root))] = plugin_json

    # 2. Write PLUGIN.md
    plugin_md = manifest_to_markdown(manifest)
    plugin_md_path = claude_dir / "PLUGIN.md"
    plugin_md_path.write_text(plugin_md, encoding="utf-8")
    written[str(plugin_md_path.relative_to(root))] = plugin_md

    # 3. Write commands/ directory
    commands_dir = claude_dir / "commands"

    if commands_content:
        # Split LLM-generated content by --- separator into individual commands
        commands_dir.mkdir(parents=True, exist_ok=True)
        sections = _split_command_sections(commands_content, manifest.commands)
        for cmd_name, content in sections.items():
            cmd_path = commands_dir / f"{cmd_name}.md"
            cmd_path.write_text(content, encoding="utf-8")
            written[str(cmd_path.relative_to(root))] = content
    elif manifest.commands:
        # Write basic command stubs from manifest data
        commands_dir.mkdir(parents=True, exist_ok=True)
        for cmd in manifest.commands:
            content = _command_stub(cmd)
            cmd_path = commands_dir / f"{cmd.name}.md"
            cmd_path.write_text(content, encoding="utf-8")
            written[str(cmd_path.relative_to(root))] = content

    return written


def _split_command_sections(
    content: str,
    commands: list[Command],
) -> dict[str, str]:
    """Split LLM-generated command content into individual command files.

    Tries to split by --- separators, falling back to heading-based splitting.
    """
    result: dict[str, str] = {}

    # Try splitting by --- separator
    sections = [s.strip() for s in content.split("\n---\n") if s.strip()]

    if len(sections) >= len(commands):
        # Match sections to commands by order
        for i, cmd in enumerate(commands):
            if i < len(sections):
                result[cmd.name] = sections[i] + "\n"
    elif sections:
        # Fewer sections than commands — try matching by heading
        for section in sections:
            for cmd in commands:
                if cmd.name in section.lower().replace(" ", "-")[:100]:
                    result[cmd.name] = section + "\n"
                    break

    # Fill in any missing commands with stubs
    for cmd in commands:
        if cmd.name not in result:
            result[cmd.name] = _command_stub(cmd)

    return result


def _command_stub(cmd: Command) -> str:
    """Generate a basic command document stub."""
    lines = [
        f"# {cmd.name}\n",
        f"> {cmd.description}\n",
    ]

    if cmd.preconditions:
        lines.append("## Preconditions\n")
        for pre in cmd.preconditions:
            lines.append(f"- {pre}")
        lines.append("")

    lines.append("## Steps\n")
    for i, step in enumerate(cmd.steps, 1):
        lines.append(f"### {i}. {step}\n")
        lines.append("<!-- Detailed instructions to be filled in -->\n")

    if cmd.verification:
        lines.append("## Verification\n")
        lines.append(f"{cmd.verification}\n")

    if cmd.skills_used:
        lines.append("## Related Skills\n")
        for skill in cmd.skills_used:
            lines.append(f"- `{skill}`")
        lines.append("")

    return "\n".join(lines) + "\n"
