"""
generator.py - Orchestrates the full pipeline:
  scan → LLM generation → write SKILL.md / AGENT.md files

Output layout (default: .claude/):
  .claude/
    skills/
      <layer>/
        SKILL.md              # layer-level skill
        <module>/SKILL.md     # per-module skill (for key modules only)
    agents/
      orchestrator/AGENT.md
      <layer>-agent/AGENT.md

Also mirrors to .opencode/ with identical structure.
"""

import sys
from pathlib import Path
from typing import Optional

from .scanner import scan_repo, classify_complexity
from .llm import build_llm, LLM
from .prompts import (
    skill_prompt,
    layer_skill_prompt,
    agent_prompt,
    orchestrator_prompt,
    build_skill_registry,
    hooks_prompt,
)


# Defaults — overridden by complexity classification at runtime
MAX_MODULE_SKILLS_PER_LAYER = 5
MIN_EXPORTS_FOR_SKILL = 2


def generate_artifacts(
    working_dir: str = ".",
    output_dir: str = ".claude",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    also_opencode: bool = True,
    verbose: bool = True,
    dry_run: bool = False,
    complexity: str = "auto",
    with_hooks: bool = False,
) -> dict:
    """
    Main entry point. Scans the repo and generates SKILL.md + AGENT.md files.

    Args:
        complexity: "auto" (detect), or force "small" / "medium" / "large".
        with_hooks: Generate HOOKS.md with Claude Code hook recommendations.

    Returns a summary dict with all generated file paths.
    """
    root = Path(working_dir).resolve()
    out = Path(output_dir) if Path(output_dir).is_absolute() else root / output_dir

    log = _make_logger(verbose)

    log(f"📂 Scanning {root} ...")
    repo_map = scan_repo(str(root))

    # Apply repoforge.yaml overrides
    cfg = repo_map.get("repoforge_config", {})
    if cfg.get("model") and model is None:
        model = cfg["model"]

    # Resolve complexity: CLI flag > config file > auto
    if complexity == "auto":
        complexity = cfg.get("complexity", "auto")
    cx = classify_complexity(repo_map, override=complexity)

    # Resolve hooks: CLI flag > config file > off
    if not with_hooks:
        with_hooks = cfg.get("generate_hooks", False)

    stats = repo_map.get("stats", {})
    rg = stats.get("rg_version", None)
    rg_status = f"ripgrep {rg}" if rg else "ripgrep not found — using fallback"
    total_files = stats.get("total_files", "?")

    layers = list(repo_map["layers"].keys())
    log(f"🗂  Layers detected: {', '.join(layers)}")
    log(f"🔧 Tech stack: {', '.join(repo_map['tech_stack'])}")
    log(f"📊 Files found: {total_files}  [{rg_status}]")
    log(f"📐 Complexity: {cx['size']} "
        f"(files={cx['total_files']}, layers={cx['num_layers']}, modules={cx['total_modules']})")
    log(f"   → skills/layer={cx['max_module_skills_per_layer']}, "
        f"min_exports={cx['min_exports_for_skill']}, "
        f"detail={cx['prompt_detail']}, "
        f"orchestrator={'yes' if cx['generate_orchestrator'] else 'skip'}, "
        f"layer_agents={'yes' if cx['generate_layer_agents'] else 'skip'}")

    llm = build_llm(model=model, api_key=api_key, api_base=api_base)
    log(f"🤖 Using model: {llm.model}")

    # Extract routing parameters from complexity
    max_skills = cx["max_module_skills_per_layer"]
    min_exports = cx["min_exports_for_skill"]
    detail = cx["prompt_detail"]

    generated = {
        "skills": [],
        "agents": [],
        "complexity": cx,
    }

    # -----------------------------------------------------------------------
    # 1. Layer-level skills
    # -----------------------------------------------------------------------
    for layer_name, layer_data in repo_map["layers"].items():
        log(f"\n✏️  Generating layer skill: {layer_name} ...")
        system, user = layer_skill_prompt(layer_name, layer_data, repo_map,
                                          prompt_detail=detail)
        content = _generate(llm, system, user, dry_run)
        path = out / "skills" / layer_name / "SKILL.md"
        _write(path, content, dry_run)
        generated["skills"].append(str(path))
        log(f"   ✅ {_rel(path, root)}")

    # -----------------------------------------------------------------------
    # 2. Per-module skills (top modules only, filtered by complexity)
    # -----------------------------------------------------------------------
    for layer_name, layer_data in repo_map["layers"].items():
        modules = _rank_modules(layer_data.get("modules", []))
        # Filter by minimum exports threshold from complexity
        eligible = [m for m in modules if len(m.get("exports", [])) >= min_exports]
        top = eligible[:max_skills]

        for module in top:
            mod_name = Path(module["path"]).stem
            log(f"✏️  Module skill: {module['path']} ...")
            system, user = skill_prompt(module, layer_name, repo_map,
                                        prompt_detail=detail)
            content = _generate(llm, system, user, dry_run)
            path = out / "skills" / layer_name / mod_name / "SKILL.md"
            _write(path, content, dry_run)
            generated["skills"].append(str(path))
            log(f"   ✅ {_rel(path, root)}")

    # -----------------------------------------------------------------------
    # 3. Layer agents (skip for small repos)
    # -----------------------------------------------------------------------
    if cx["generate_layer_agents"]:
        for layer_name, layer_data in repo_map["layers"].items():
            log(f"\n🤖 Generating agent: {layer_name}-agent ...")
            layer_skills = [
                p for p in generated["skills"]
                if f"/skills/{layer_name}/" in p
            ]
            system, user = agent_prompt(
                layer_name, layer_data, repo_map, layers,
                generated_skills=layer_skills,
            )
            content = _generate(llm, system, user, dry_run)
            path = out / "agents" / f"{layer_name}-agent" / "AGENT.md"
            _write(path, content, dry_run)
            generated["agents"].append(str(path))
            log(f"   ✅ {_rel(path, root)}")
    else:
        log("\n⏭️  Skipping layer agents (small repo)")

    # -----------------------------------------------------------------------
    # 4. Orchestrator agent (skip for small repos)
    # -----------------------------------------------------------------------
    if cx["generate_orchestrator"]:
        log("\n🤖 Generating orchestrator agent ...")
        system, user = orchestrator_prompt(repo_map)
        content = _generate(llm, system, user, dry_run)
        path = out / "agents" / "orchestrator" / "AGENT.md"
        _write(path, content, dry_run)
        generated["agents"].append(str(path))
        log(f"   ✅ {_rel(path, root)}")
    else:
        log("\n⏭️  Skipping orchestrator (small repo)")

    # -----------------------------------------------------------------------
    # 5. Generate skill-registry.md (agent-teams-lite compatible)
    # -----------------------------------------------------------------------
    log("\n📋 Generating skill registry...")
    registry_content = build_skill_registry(
        generated_skills=generated["skills"],
        repo_map=repo_map,
        output_root=out,
        project_root=root,
    )
    registry_path = root / ".atl" / "skill-registry.md"
    if not dry_run:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(registry_content, encoding="utf-8")
        # Add .atl/ to .gitignore if not already there
        _update_gitignore(root, ".atl/")
    generated["registry"] = str(registry_path)
    log(f"   ✅ {_rel(registry_path, root)}")

    # -----------------------------------------------------------------------
    # 6. Hooks documentation (opt-in via --with-hooks or config)
    # -----------------------------------------------------------------------
    if with_hooks:
        log("\n🪝 Generating hooks documentation...")
        system, user = hooks_prompt(repo_map, cx)
        content = _generate(llm, system, user, dry_run)
        hooks_path = out / "hooks" / "HOOKS.md"
        _write(hooks_path, content, dry_run)
        generated["hooks"] = str(hooks_path)
        log(f"   ✅ {_rel(hooks_path, root)}")
    else:
        log("\n⏭️  Skipping hooks (use --with-hooks to enable)")

    # -----------------------------------------------------------------------
    # 7. Mirror to .opencode/ if requested
    # -----------------------------------------------------------------------
    if also_opencode and not dry_run:
        opencode_out = root / ".opencode"
        _mirror(out, opencode_out, log)
        log(f"\n📁 Also mirrored to {_rel(opencode_out, root)}")

    # -----------------------------------------------------------------------
    # 8. Write index
    # -----------------------------------------------------------------------
    _write_index(out, repo_map, generated, dry_run)

    log(f"\n🎉 Done! Generated {len(generated['skills'])} skills, {len(generated['agents'])} agents")
    log(f"   Output: {_rel(out, root)}")

    return generated


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate(llm: LLM, system: str, user: str, dry_run: bool) -> str:
    if dry_run:
        return f"# DRY RUN\n\nWould call {llm.model} here.\n"
    return llm.complete(user, system=system)


def _write(path: Path, content: str, dry_run: bool):
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _mirror(src: Path, dst: Path, log):
    """Copy all generated files to .opencode/ preserving structure."""
    import shutil
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _rank_modules(modules: list) -> list:
    """
    Rank modules by interest level for skill generation.

    High value: endpoints, services, hooks, domain logic with many exports
    Low value:  index barrel files, constants, types-only, test files
    """
    # Filename patterns that signal high business value (generic, framework-agnostic)
    HIGH_VALUE_NAMES = {
        # Common high-value backend patterns
        "auth", "authentication", "authorization",
        "api", "router", "routes", "endpoints", "handler", "handlers",
        "service", "services", "repository", "repositories",
        "middleware", "interceptor",
        "model", "models", "schema", "schemas",
        "controller", "controllers",
        "database", "db", "store",
        "queue", "worker", "job", "task",
        "gateway", "client",
        # Common high-value frontend patterns
        "app", "main", "core", "root",
        "store", "context", "provider",
        "hooks", "composables",
        "layout", "router",
    }

    # Filename patterns that signal low value
    LOW_VALUE_NAMES = {
        "__init__", "index", "constants", "types", "config",
        "accessibility", "icons", "basePath", "env",
    }

    def score(m: dict) -> float:
        s = 0.0
        name = m["name"]
        path = m["path"]

        # Export count — primary signal
        s += len(m.get("exports", [])) * 2.0

        # Summary hint — signals well-documented module
        if m.get("summary_hint"):
            s += 3.0

        # High-value name match
        if name in HIGH_VALUE_NAMES:
            s += 8.0

        # Path signals: endpoints/, services/, hooks/ directories are valuable
        if any(d in path for d in ("/endpoints/", "/services/", "/hooks/", "/api/",
                                    "/routers/", "/controllers/", "/handlers/",
                                    "/composables/", "/store/", "/stores/")):
            s += 5.0

        # Low value names
        if name in LOW_VALUE_NAMES:
            s -= 10.0

        # Test / spec files
        if "test" in path.lower() or "spec" in path.lower():
            s -= 15.0

        # Barrel index.ts with only re-exports
        if name == "index" and len(m.get("exports", [])) > 5:
            s -= 8.0  # likely a barrel file

        # Penalize pure types/constants files
        if name in ("types", "constants") and not m.get("summary_hint"):
            s -= 5.0

        return s

    return sorted(modules, key=score, reverse=True)


def _write_index(out: Path, repo_map: dict, generated: dict, dry_run: bool):
    """Write a SKILLS_INDEX.md listing everything that was generated."""
    lines = [
        "# RepoForge — Generated artifacts index\n",
        f"**Tech stack:** {', '.join(repo_map['tech_stack'])}\n",
        f"**Layers:** {', '.join(repo_map['layers'].keys())}\n",
        "\n## Skills\n",
    ]
    for p in generated.get("skills", []):
        lines.append(f"- `{p}`\n")
    lines.append("\n## Agents\n")
    for p in generated.get("agents", []):
        lines.append(f"- `{p}`\n")
    if generated.get("registry"):
        lines.append("\n## Skill Registry\n")
        lines.append(f"- `{generated['registry']}`\n")
    if generated.get("hooks"):
        lines.append("\n## Hooks\n")
        lines.append(f"- `{generated['hooks']}`\n")
    lines.append("\n## Usage\n")
    lines.append("In Claude Code, skills and agents in `.claude/` are loaded automatically.\n")
    lines.append("In OpenCode, use `.opencode/` — same structure.\n")
    lines.append("Skill registry at `.atl/skill-registry.md` is read by sub-agents automatically.\n")

    _write(out / "SKILLS_INDEX.md", "".join(lines), dry_run)


def _rel(path: Path, root: Path) -> str:
    """Safe relative path — falls back to absolute if path is outside root."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _update_gitignore(root: Path, entry: str):
    """Add entry to .gitignore if not already present."""
    gitignore = root / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        if entry not in content:
            gitignore.write_text(content.rstrip() + f"\n{entry}\n", encoding="utf-8")
    else:
        gitignore.write_text(f"{entry}\n", encoding="utf-8")


def _make_logger(verbose: bool):
    if verbose:
        return lambda msg: print(msg, file=sys.stderr)
    return lambda msg: None
