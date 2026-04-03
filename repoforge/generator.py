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

Multi-tool targets (via --targets flag):
  cursor  → .cursor/rules/<name>.mdc
  codex   → AGENTS.md (project root)
  gemini  → GEMINI.md (project root)
  copilot → .github/copilot-instructions.md
"""

import logging
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
from .adapters import resolve_targets, run_adapters, ADAPTER_TARGETS
from .disclosure import build_discovery_index
from .plugins import build_plugin_manifest, write_plugin, commands_prompt
from .graph_context import (
    build_graph_context_from_graph,
    build_short_graph_context,
    build_module_graph_context,
    build_semantic_context,
    build_module_facts_context,
    format_facts_section,
)


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token budget constants
# ---------------------------------------------------------------------------

_CHARS_PER_TOKEN = 4
# Conservative default: most models handle ≥128k input tokens.
# The budget leaves room for the LLM's output (max_tokens) on top.
_DEFAULT_INPUT_TOKEN_BUDGET = 120_000


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
    with_plugin: bool = False,
    targets: Optional[str] = None,
    disclosure: str = "tiered",
    compress: bool = False,
    compress_aggressive: bool = False,
    scan: bool = False,
) -> dict:
    """
    Main entry point. Scans the repo and generates SKILL.md + AGENT.md files.

    Args:
        complexity: "auto" (detect), or force "small" / "medium" / "large".
        with_hooks: Generate HOOKS.md with Claude Code hook recommendations.
        with_plugin: Generate plugin.json + commands/ + PLUGIN.md hierarchy.
        targets: Comma-separated list of output targets.
                 Default: "claude,opencode". Use "all" for all targets.
                 Valid: claude, opencode, cursor, codex, gemini, copilot.
        disclosure: "full" (no tier markers) | "tiered" (add L1/L2/L3 markers).
                    Default: "tiered" (progressive disclosure enabled).
        compress: After generation, run token compressor on generated skills.
        compress_aggressive: Use aggressive abbreviation mode for compression.
        scan: After generation (and compression), run security scanner.

    Returns a summary dict with all generated file paths.
    """
    root = Path(working_dir).resolve()
    out = Path(output_dir) if Path(output_dir).is_absolute() else root / output_dir

    log = _make_logger(verbose)

    # Resolve targets: --targets flag > config file > legacy also_opencode default
    if targets is None:
        # Will be resolved after config is loaded (see below)
        _targets_from_cli = None
    else:
        _targets_from_cli = targets

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

    # Resolve plugin: CLI flag > config file > off
    if not with_plugin:
        with_plugin = cfg.get("generate_plugin", False)

    # Resolve disclosure: CLI flag > config file > tiered (default)
    if disclosure == "tiered":
        disclosure = cfg.get("disclosure", "tiered")

    # Resolve targets: CLI --targets > config targets > legacy also_opencode default
    if _targets_from_cli is not None:
        active_targets = resolve_targets(_targets_from_cli)
    elif cfg.get("targets"):
        # Config file: targets: [claude, opencode, cursor]
        cfg_targets = cfg["targets"]
        if isinstance(cfg_targets, list):
            active_targets = resolve_targets(",".join(cfg_targets))
        else:
            active_targets = resolve_targets(str(cfg_targets))
    else:
        # Legacy default: claude + opencode (unless --no-opencode was set)
        active_targets = ["claude", "opencode"] if also_opencode else ["claude"]

    # Override also_opencode based on resolved targets
    also_opencode = "opencode" in active_targets

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
        f"disclosure={disclosure}, "
        f"orchestrator={'yes' if cx['generate_orchestrator'] else 'skip'}, "
        f"layer_agents={'yes' if cx['generate_layer_agents'] else 'skip'}")

    if dry_run:
        # In dry-run mode, skip LLM initialization entirely (no API key needed)
        llm = LLM(model=model or "(dry-run)")
        log(f"🤖 Model: {llm.model} (dry-run — no LLM calls)")
    else:
        llm = build_llm(model=model, api_key=api_key, api_base=api_base)
        log(f"🤖 Using model: {llm.model}")

    # Extract routing parameters from complexity
    max_skills = cx["max_module_skills_per_layer"]
    min_exports = cx["min_exports_for_skill"]
    detail = cx["prompt_detail"]

    # Build dependency graph (cached, reused for all skills)
    _graph = None
    _graph_ctx = ""
    try:
        from .graph import build_graph_v2
        log(f"\n🔗 Building dependency graph...")
        _graph = build_graph_v2(str(root))
        _graph_ctx = build_short_graph_context(_graph)
        module_count = len([n for n in _graph.nodes if n.node_type == "module"])
        edge_count = len([e for e in _graph.edges if e.edge_type in ("imports", "depends_on")])
        log(f"   ✅ Graph: {module_count} modules, {edge_count} dependencies")
    except (ImportError, OSError, ValueError, RuntimeError) as e:
        # ImportError: graph module not available; OSError: file access errors
        # ValueError: parse failures; RuntimeError: graph construction errors
        log(f"   ⚠️  Graph analysis skipped: {e}")

    # Extract semantic facts (cached, reused for all skills)
    _all_files = [
        m["path"]
        for layer in repo_map["layers"].values()
        for m in layer.get("modules", [])
    ]
    _facts_ctx = ""
    try:
        log(f"🔍 Extracting semantic facts...")
        from .facts import extract_facts as _extract_facts
        _all_facts = _extract_facts(str(root), _all_files)
        _facts_ctx = format_facts_section(_all_facts)
        if _all_facts:
            log(f"   ✅ Facts: {len(_all_facts)} items extracted")
        else:
            log(f"   ℹ️  No semantic facts found")
    except (ImportError, OSError, ValueError) as e:
        # ImportError: facts module not available; OSError: file read errors
        # ValueError: parse failures in fact extraction
        log(f"   ⚠️  Fact extraction skipped: {e}")

    generated = {
        "skills": [],
        "agents": [],
        "complexity": cx,
        "disclosure": disclosure,
    }

    # -----------------------------------------------------------------------
    # 1. Layer-level skills
    # -----------------------------------------------------------------------
    for layer_name, layer_data in repo_map["layers"].items():
        log(f"\n✏️  Generating layer skill: {layer_name} ...")
        # Layer skills get graph context + global facts
        _layer_ctx = (_facts_ctx + "\n" + _graph_ctx).strip() if _facts_ctx else _graph_ctx
        system, user = layer_skill_prompt(layer_name, layer_data, repo_map,
                                          prompt_detail=detail,
                                          disclosure=disclosure,
                                          graph_context=_layer_ctx)
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
            # Build per-module blast radius + module-specific facts
            mod_graph_ctx = ""
            if _graph is not None:
                mod_graph_ctx = build_module_graph_context(_graph, module["path"])
            mod_facts_ctx = build_module_facts_context(str(root), module["path"], _all_files)
            # Combine: module facts + blast radius
            mod_ctx = (mod_facts_ctx + "\n" + mod_graph_ctx).strip() if mod_facts_ctx else mod_graph_ctx
            system, user = skill_prompt(module, layer_name, repo_map,
                                        prompt_detail=detail,
                                        disclosure=disclosure,
                                        graph_context=mod_ctx)
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
    # 5b. Discovery index (when disclosure=tiered)
    # -----------------------------------------------------------------------
    if disclosure == "tiered" and not dry_run:
        skills_dir = out / "skills"
        if skills_dir.exists():
            log("\n📇 Generating discovery index...")
            discovery_content = build_discovery_index(str(skills_dir))
            discovery_path = out / "skills" / "DISCOVERY_INDEX.md"
            _write(discovery_path, discovery_content, dry_run)
            generated["discovery_index"] = str(discovery_path)
            log(f"   ✅ {_rel(discovery_path, root)}")
    elif disclosure == "tiered" and dry_run:
        log("\n📇 Discovery index would be generated (skipped in dry-run)")

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
    # 6b. Plugin hierarchy (opt-in via --plugin or config)
    # -----------------------------------------------------------------------
    if with_plugin:
        log("\n📦 Generating plugin manifest and commands...")
        manifest = build_plugin_manifest(repo_map, generated, cx)

        if not dry_run:
            # Optionally generate detailed command workflows via LLM
            cmd_prompt = commands_prompt(repo_map, cx)
            cmd_content = ""
            if cmd_prompt and manifest.commands:
                log("   ✏️  Generating detailed command workflows...")
                cmd_content = llm.complete(cmd_prompt, system=(
                    "Output ONLY the command workflow documents. "
                    "No preamble, no explanation. "
                    "Separate each command with ---."
                ))

            plugin_files = write_plugin(str(root), manifest, cmd_content)
            generated["plugin"] = {
                "manifest": str(root / ".claude" / "plugin.json"),
                "readme": str(root / ".claude" / "PLUGIN.md"),
                "commands": [
                    p for p in plugin_files
                    if p.startswith(".claude/commands/")
                ],
                "total_commands": len(manifest.commands),
            }
            log(f"   ✅ plugin.json ({len(manifest.commands)} commands)")
            log("   ✅ PLUGIN.md")
            for cmd_path in generated["plugin"]["commands"]:
                log(f"   ✅ {cmd_path}")
        else:
            manifest = build_plugin_manifest(repo_map, generated, cx)
            generated["plugin"] = {
                "manifest": str(root / ".claude" / "plugin.json"),
                "readme": str(root / ".claude" / "PLUGIN.md"),
                "commands": [f".claude/commands/{cmd.name}.md" for cmd in manifest.commands],
                "total_commands": len(manifest.commands),
            }
            log(f"   📦 Would generate plugin.json + {len(manifest.commands)} commands (dry-run)")
    else:
        log("\n⏭️  Skipping plugin generation (use --plugin to enable)")

    # -----------------------------------------------------------------------
    # 7. Mirror to .opencode/ if requested
    # -----------------------------------------------------------------------
    if also_opencode and not dry_run:
        opencode_out = root / ".opencode"
        _mirror(out, opencode_out, log)
        log(f"\n📁 Also mirrored to {_rel(opencode_out, root)}")

    # -----------------------------------------------------------------------
    # 7b. Multi-tool adapter outputs (cursor, codex, gemini, copilot)
    # -----------------------------------------------------------------------
    adapter_targets = [t for t in active_targets if t in ADAPTER_TARGETS]
    if adapter_targets:
        log(f"\n🔀 Generating multi-tool output: {', '.join(adapter_targets)}")

        # Read back generated skill/agent contents for adapter input
        skill_contents = _collect_contents(generated.get("skills", []), out, root, dry_run)
        agent_contents = _collect_contents(generated.get("agents", []), out, root, dry_run)

        adapter_output = run_adapters(
            targets=adapter_targets,
            skills=skill_contents,
            agents=agent_contents if agent_contents else None,
            repo_map=repo_map,
        )

        # Write adapter outputs
        adapter_paths: list[str] = []
        for rel_path, content in adapter_output.items():
            full_path = root / rel_path
            _write(full_path, content, dry_run)
            adapter_paths.append(rel_path)
            log(f"   ✅ {rel_path}")

        generated["adapter_targets"] = adapter_targets
        generated["adapter_outputs"] = adapter_paths

    # -----------------------------------------------------------------------
    # 8. Write index
    # -----------------------------------------------------------------------
    _write_index(out, repo_map, generated, dry_run)

    # -----------------------------------------------------------------------
    # 9. Token compression (opt-in via --compress flag)
    # -----------------------------------------------------------------------
    if compress and not dry_run:
        from .compressor import compress_directory
        skills_dir = out / "skills"
        if skills_dir.exists():
            log("\n🗜️  Compressing generated skills...")
            results = compress_directory(str(skills_dir), aggressive=compress_aggressive)
            if results:
                mode = "aggressive" if compress_aggressive else "normal"
                total_orig = sum(r.original_tokens for r in results)
                total_comp = sum(r.compressed_tokens for r in results)
                ratio = total_comp / total_orig if total_orig > 0 else 1.0
                pct = (1.0 - ratio) * 100 if ratio < 1.0 else 0.0
                log(f"   Compressed {len(results)} files (mode={mode}): "
                    f"{total_orig} → {total_comp} tokens ({pct:.1f}% reduction)")
                generated["compression"] = {
                    "files": len(results),
                    "mode": mode,
                    "original_tokens": total_orig,
                    "compressed_tokens": total_comp,
                    "ratio": round(ratio, 3),
                }
    elif compress and dry_run:
        log("\n🗜️  Compression would run after generation (skipped in dry-run)")

    # -----------------------------------------------------------------------
    # 10. Security scan (opt-in via --scan flag or scan parameter)
    # -----------------------------------------------------------------------
    if scan and not dry_run:
        from .security import scan_generated_output, SecurityScanner
        log("\n🔒 Running security scan on generated output...")
        scan_result = scan_generated_output(str(root))
        if scan_result.findings:
            scanner = SecurityScanner()
            log(scanner.report(scan_result, fmt="table"))
        else:
            log("   ✅ No security issues found.")
        generated["security_scan"] = {
            "files_scanned": scan_result.files_scanned,
            "passed": scan_result.passed,
            "critical": scan_result.critical_count,
            "high": scan_result.high_count,
            "medium": scan_result.medium_count,
            "low": scan_result.low_count,
            "info": scan_result.info_count,
            "total_findings": len(scan_result.findings),
        }
    elif scan and dry_run:
        log("\n🔒 Security scan would run after generation (skipped in dry-run)")

    targets_summary = ", ".join(active_targets)
    plugin_summary = ""
    if generated.get("plugin"):
        plugin_summary = f", {generated['plugin']['total_commands']} commands (plugin)"

    if dry_run:
        log(f"\n🔍 DRY RUN — no LLM calls, no files written")
        log(f"   Would generate {len(generated['skills'])} skills, {len(generated['agents'])} agents{plugin_summary}")
        log(f"   Targets: {targets_summary}")
        log(f"   Output: {_rel(out, root)}")
    else:
        log(f"\n🎉 Done! Generated {len(generated['skills'])} skills, {len(generated['agents'])} agents{plugin_summary}")
        log(f"   Targets: {targets_summary}")
        log(f"   Output: {_rel(out, root)}")

    return generated


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_contents(
    paths: list[str], output_root: Path, project_root: Path, dry_run: bool,
) -> dict[str, str]:
    """
    Read back generated files and return {relative_path: content}.

    Relative paths are computed from the output_root (e.g. "backend/SKILL.md").
    In dry-run mode, returns placeholder content keyed by the relative path.
    """
    result: dict[str, str] = {}
    for abs_path_str in paths:
        abs_path = Path(abs_path_str)
        # Compute relative to output_root for skill paths
        try:
            # Try relative to output_root first (skills/ and agents/ structure)
            rel = str(abs_path.relative_to(output_root))
        except ValueError:
            # Fallback to project root
            try:
                rel = str(abs_path.relative_to(project_root))
            except ValueError:
                rel = abs_path.name

        if dry_run:
            result[rel] = f"# DRY RUN placeholder for {rel}\n"
        elif abs_path.exists():
            result[rel] = abs_path.read_text(encoding="utf-8")
    return result


def _estimate_prompt_tokens(text: str) -> int:
    """Rough token estimate consistent with intelligence.budget (~4 chars/token)."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _generate(
    llm: LLM,
    system: str,
    user: str,
    dry_run: bool,
    input_budget: int = _DEFAULT_INPUT_TOKEN_BUDGET,
) -> str:
    """Call the LLM with token-budget enforcement.

    Before every LLM call, estimates the combined prompt size (system + user).
    If over budget, truncates the *user* prompt to fit and logs a warning.
    The system prompt is never truncated — it contains essential instructions.
    """
    if dry_run:
        return f"# DRY RUN\n\nWould call {llm.model} here.\n"

    system_tokens = _estimate_prompt_tokens(system)
    user_tokens = _estimate_prompt_tokens(user)
    total_tokens = system_tokens + user_tokens

    if total_tokens > input_budget:
        # Reserve space for the system prompt; truncate user prompt to fit
        available_for_user = max(0, input_budget - system_tokens)
        char_limit = available_for_user * _CHARS_PER_TOKEN
        original_user_tokens = user_tokens
        user = user[:char_limit]
        user_tokens = _estimate_prompt_tokens(user)
        logger.warning(
            "Token budget exceeded: %d tokens (system=%d + user=%d) > budget=%d. "
            "User prompt truncated from %d to %d tokens.",
            total_tokens, system_tokens, original_user_tokens,
            input_budget, original_user_tokens, user_tokens,
        )

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
    if generated.get("discovery_index"):
        lines.append("\n## Discovery Index\n")
        lines.append(f"- `{generated['discovery_index']}`\n")
        lines.append("  Load this first — lightweight index of all skills for agent discovery.\n")
    if generated.get("plugin"):
        plugin = generated["plugin"]
        lines.append("\n## Plugin\n")
        lines.append(f"- `{plugin['manifest']}`\n")
        lines.append(f"- `{plugin['readme']}`\n")
        for cmd_path in plugin.get("commands", []):
            lines.append(f"- `{cmd_path}`\n")
        lines.append(f"  Plugin with {plugin['total_commands']} commands.\n")
    # Multi-tool adapter outputs
    adapter_outputs = generated.get("adapter_outputs", [])
    if adapter_outputs:
        lines.append("\n## Multi-Tool Outputs\n")
        for p in adapter_outputs:
            lines.append(f"- `{p}`\n")
    lines.append("\n## Usage\n")
    lines.append("In Claude Code, skills and agents in `.claude/` are loaded automatically.\n")
    lines.append("In OpenCode, use `.opencode/` — same structure.\n")
    if any("cursor" in p for p in adapter_outputs):
        lines.append("In Cursor, rules in `.cursor/rules/` are loaded based on file globs.\n")
    if any(p == "AGENTS.md" for p in adapter_outputs):
        lines.append("In Codex / OpenAI, `AGENTS.md` is loaded as project instructions.\n")
    if any(p == "GEMINI.md" for p in adapter_outputs):
        lines.append("In Gemini CLI, `GEMINI.md` is loaded as project instructions.\n")
    if any("copilot" in p for p in adapter_outputs):
        lines.append("In GitHub Copilot, `.github/copilot-instructions.md` provides context.\n")
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
