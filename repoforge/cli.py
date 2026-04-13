"""
cli.py - Command-line interface for RepoForge.

Six modes:

  repoforge skills           [options] — Generate SKILL.md + AGENT.md for Claude Code / OpenCode
  repoforge skills-from-docs [options] — Generate SKILL.md from documentation sources
  repoforge score            [options] — Score quality of generated SKILL.md files (no API key needed)
  repoforge scan             [options] — Security scan generated output for issues (no API key needed)
  repoforge docs             [options] — Generate technical documentation (Docsify / GH Pages ready)
  repoforge export           [options] — Flatten repo into a single LLM-optimized file (no API key needed)
  repoforge compress         [options] — Token-optimize generated .md files (no API key needed)
  repoforge prompts          [options] — Generate reusable analysis prompts from codebase scan (no API key needed)
  repoforge check            [options] — Validate code references in generated docs (no API key needed)
  repoforge diff             REF_A REF_B — Entity-level semantic diff between git refs (no API key needed)
  repoforge index            [options] — Build semantic search index from codebase entities (requires API key)
  repoforge query            QUERY     — Search the semantic index for matching entities (requires API key)

Quick usage:
  repoforge skills -w /my/repo --model claude-haiku-3-5
  repoforge skills -w /my/repo --targets all            # generate for all AI tools
  repoforge skills -w /my/repo --targets claude,cursor   # Claude + Cursor only
  repoforge skills -w /my/repo --compress                # generate + auto-compress
  repoforge skills -w /my/repo --scan                    # generate + auto-security-scan
  repoforge skills -w /my/repo --plugin                  # generate + plugin hierarchy
  repoforge score  -w /my/repo --format table
  repoforge scan   -w /my/repo --format table
  repoforge scan   -w /my/repo --fail-on critical
  repoforge docs   -w /my/repo --lang Spanish -o docs
  repoforge docs   -w /my/repo --model gpt-4o-mini --lang English --dry-run
  repoforge export -w /my/repo -o context.md
  repoforge export -w /my/repo --max-tokens 100000 --format xml
  repoforge compress -w /my/repo --aggressive --dry-run
  repoforge skills --model ollama/qwen2.5-coder:14b   # free local
  repoforge skills --model github/gpt-4o-mini          # GitHub Copilot
  repoforge skills --model gateway/claude-sonnet-4     # via mcp-llm-bridge
"""

import logging

import click

# ---------------------------------------------------------------------------
# Shared options factory
# ---------------------------------------------------------------------------

def _common_options(f):
    """Decorator that adds common options to both subcommands."""
    f = click.option("-w", "--working-dir",
        default=".", show_default=True,
        help="Path to the repo to analyze.",
        type=click.Path(exists=True, file_okay=False),
    )(f)
    f = click.option("--model", default=None, help=(
        "LLM to use. Examples: claude-haiku-3-5, gpt-4o-mini, "
        "groq/llama-3.1-70b-versatile, ollama/qwen2.5-coder:14b, github/gpt-4o-mini. "
        "Auto-detects from env vars if not set."
    ))(f)
    f = click.option("--api-key", default=None, help="Override API key.")(f)
    f = click.option("--api-base", default=None, help="Override API base URL.")(f)
    f = click.option("--dry-run", is_flag=True, default=False,
        help="Scan and plan, but don't call the LLM or write files.")(f)
    f = click.option("-q", "--quiet", is_flag=True, default=False,
        help="Suppress progress output.")(f)
    f = click.option("--max-files", "max_files_per_layer", default=None, type=int,
        help=(
            "Max files per layer during scanning. "
            "Default: 500. Previously hardcoded to 80, which silently dropped files. "
            "Token budget enforcement now happens downstream, so this cap is just a safety rail."
        ))(f)
    return f


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="repoforge-ai")
@click.option("-v", "--verbose", count=True, help="Increase verbosity (-v INFO, -vv DEBUG).")
def main(verbose):
    """
    RepoForge — AI-powered code analysis tool.

    \b
    Commands:
      skills           Generate SKILL.md + AGENT.md for Claude Code / OpenCode
      skills-from-docs Generate SKILL.md from documentation (URL, GitHub, PDF, YouTube, notebook)
      import-docs      Import external dependency docs for context enrichment (no API key needed)
      score            Score quality of generated SKILL.md files (no API key needed)
      scan             Security scan generated output for issues (no API key needed)
      docs             Generate technical documentation (Docsify-ready, GH Pages compatible)
      export           Flatten repo into a single LLM-optimized file (no API key needed)
      compress         Token-optimize generated .md files (no API key needed)
      graph            Build a code knowledge graph from scanner data (no API key needed)
      prompts          Generate reusable analysis prompts from codebase scan (no API key needed)
      check            Validate code references in generated docs (no API key needed)
      diff             Entity-level semantic diff between two git refs (no API key needed)
      validate-skills  Validate SKILL.md files against standard format (no API key needed)
      blast-radius     Compute transitive blast radius of a change (no API key needed)
      change-impact    Identify which tests need to run for a change (no API key needed)
      co-change        Detect files that always change together (no API key needed)
      ownership        Compute file/module ownership and bus factor (no API key needed)

    \b
    Examples:
      repoforge skills -w .
      repoforge skills -w . --compress
      repoforge skills -w . --scan
      repoforge score -w . --format table
      repoforge score -w . --min-score 0.7
      repoforge scan -w . --format table
      repoforge scan -w . --fail-on critical
      repoforge docs -w . --lang Spanish -o docs
      repoforge docs --model gpt-4o-mini --dry-run
      repoforge export -w . -o context.md
      repoforge export -w . --max-tokens 100000 --format xml
      repoforge compress -w . --aggressive --dry-run
      repoforge graph -w . --format mermaid
      repoforge graph -w . --blast-radius src/auth.py
      repoforge import-docs --npm react --pypi click
      repoforge skills-from-docs -w https://docs.example.com -o .claude/skills
      repoforge skills-from-docs -w /path/to/docs --name my-lib
    """
    level = logging.WARNING
    if verbose >= 2:
        level = logging.DEBUG
    elif verbose == 1:
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )


# ---------------------------------------------------------------------------
# skills subcommand
# ---------------------------------------------------------------------------

@main.command()
@_common_options
@click.option("-o", "--output-dir", default=".claude", show_default=True,
    help="Output directory for skills and agents.")
@click.option("--no-opencode", is_flag=True, default=False,
    help="Skip mirroring output to .opencode/ directory.")
@click.option("--complexity",
    default="auto", show_default=True,
    type=click.Choice(["auto", "small", "medium", "large"], case_sensitive=False),
    help="Override auto-detected repo complexity (affects generation depth).")
@click.option("--serve", "do_serve", is_flag=True, default=False,
    help="After generating, open the skills browser.")
@click.option("--port", default=8765, show_default=True,
    help="Port for --serve mode.")
@click.option("--serve-only", is_flag=True, default=False,
    help="Skip generation, only open browser for existing skills.")
@click.option("--with-hooks/--no-hooks", default=False, show_default=True,
    help="Generate HOOKS.md with recommended Claude Code hooks.")
@click.option("--score/--no-score", "do_score", default=False, show_default=True,
    help="After generation, score quality of generated SKILL.md files.")
@click.option("--targets", default=None,
    help=(
        "Comma-separated list of output targets. "
        "Default: claude,opencode. "
        "Valid: claude, opencode, cursor, codex, gemini, copilot, all."
    ))
@click.option("--disclosure",
    default="tiered", show_default=True,
    type=click.Choice(["full", "tiered"], case_sensitive=False),
    help="Skill output mode: tiered (progressive disclosure markers) or full (no markers).")
@click.option("--compress/--no-compress", "do_compress", default=False, show_default=True,
    help="After generation, compress skills to reduce token count.")
@click.option("--aggressive", is_flag=True, default=False,
    help="Use aggressive compression (abbreviations). Only applies with --compress.")
@click.option("--scan/--no-scan", "do_scan", default=False, show_default=True,
    help="After generation, run security scanner on generated output.")
@click.option("--plugin/--no-plugin", "with_plugin", default=False, show_default=True,
    help="Generate plugin.json + commands/ hierarchy (Skills → Commands → Plugins).")
def skills(working_dir, model, api_key, api_base, dry_run, quiet,
           max_files_per_layer,
           output_dir, no_opencode, complexity, do_serve, port, serve_only,
           with_hooks, do_score, targets, disclosure, do_compress, aggressive,
           do_scan, with_plugin):
    """
    Generate SKILL.md and AGENT.md files from your codebase.

    \b
    Output layout (default: .claude/):
      .claude/
        skills/<layer>/SKILL.md
        skills/<layer>/<module>/SKILL.md
        agents/<layer>-agent/AGENT.md
        agents/orchestrator/AGENT.md

    Also mirrors to .opencode/ unless --no-opencode is set.

    \b
    Multi-tool output (via --targets):
      cursor  → .cursor/rules/<name>.mdc
      codex   → AGENTS.md (project root)
      gemini  → GEMINI.md (project root)
      copilot → .github/copilot-instructions.md
    """
    from .generator import generate_artifacts
    from .server import serve_skills

    if not serve_only:
        generate_artifacts(
            working_dir=working_dir,
            output_dir=output_dir,
            model=model,
            api_key=api_key,
            api_base=api_base,
            also_opencode=not no_opencode,
            verbose=not quiet,
            dry_run=dry_run,
            complexity=complexity,
            with_hooks=with_hooks,
            with_plugin=with_plugin,
            targets=targets,
            disclosure=disclosure,
            compress=do_compress,
            compress_aggressive=aggressive,
        )

    if do_score and not dry_run:
        from pathlib import Path as _Path

        from .scorer import SkillScorer
        out_path = (
            _Path(output_dir) if _Path(output_dir).is_absolute()
            else _Path(working_dir) / output_dir
        )
        skills_dir = out_path / "skills"
        if skills_dir.exists():
            scorer = SkillScorer()
            scores = scorer.score_directory(str(skills_dir))
            if scores:
                click.echo(scorer.report(scores, fmt="table"), err=True)

    if do_scan and not dry_run:
        from .security import scan_generated_output
        scan_result = scan_generated_output(working_dir)
        if scan_result.findings:
            from .security import SecurityScanner
            scanner = SecurityScanner()
            click.echo(scanner.report(scan_result, fmt="table"), err=True)
        elif not quiet:
            click.echo("\n\u2705 Security scan: no issues found.", err=True)

    if do_serve or serve_only:
        from pathlib import Path
        out = Path(output_dir) if Path(output_dir).is_absolute() else Path(working_dir) / output_dir
        serve_skills(str(out), port=port, open_browser=True)


# ---------------------------------------------------------------------------
# docs subcommand
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES = [
    "English", "Spanish", "French", "German", "Portuguese",
    "Chinese", "Japanese", "Korean", "Russian", "Italian", "Dutch",
]


@main.command()
@_common_options
@click.option("-o", "--output-dir", default="docs", show_default=True,
    help="Output directory for documentation files.")
@click.option("--lang", "--language", "language",
    default="English", show_default=True,
    type=click.Choice(SUPPORTED_LANGUAGES, case_sensitive=False),
    help="Language for the generated documentation.")
@click.option("--name", "project_name", default=None,
    help="Project name override (auto-detected from config files by default).")
@click.option("--complexity",
    default="auto", show_default=True,
    type=click.Choice(["auto", "small", "medium", "large"], case_sensitive=False),
    help="Override auto-detected repo complexity (affects chapter count).")
@click.option("--theme", default="vue", show_default=True,
    type=click.Choice(["vue", "dark", "buble", "pure"], case_sensitive=False),
    help="Docsify visual theme.")
@click.option("--serve", "do_serve", is_flag=True, default=False,
    help="After generating, serve the docs locally (opens browser).")
@click.option("--port", default=8000, show_default=True,
    help="Port for --serve mode.")
@click.option("--serve-only", is_flag=True, default=False,
    help="Skip generation, only serve existing docs in output-dir.")
@click.option("--chunked", is_flag=True, default=False,
    help="Use chunked doc generation (pre-digested per-chapter data). Default: full-context mode.")
@click.option("--verify/--no-verify", "do_verify", default=True, show_default=True,
    help="Enable/disable LLM verification of generated chapters (Stage C).")
@click.option("--verify-model", default=None,
    help="Model for verification. Default: github/Phi-4 (or gpt-4o-mini if generator is Phi-4).")
@click.option("--no-verify-docs", is_flag=True, default=False,
    help="Disable BOTH deterministic corrections (Stage D) and LLM verification (Stage C).")
@click.option("--facts-only/--no-facts-only", default=False, show_default=True,
    help="Generate only the factual extraction (no LLM prose). Outputs structured facts per chapter.")
@click.option("--incremental/--no-incremental", default=False, show_default=True,
    help="Only regenerate chapters whose source files changed since last run (uses git diff + manifest).")
@click.option("--semantic-dedup/--no-semantic-dedup", default=False, show_default=True,
    help="Use embedding similarity to skip chapters whose source meaning hasn't changed (requires --incremental).")
@click.option("--semantic-threshold", default=0.95, show_default=True, type=float,
    help="Cosine similarity threshold for --semantic-dedup (0.0-1.0). Higher = more aggressive skipping.")
@click.option("--watch", is_flag=True, default=False,
    help="Enter watch mode: poll source files and regenerate docs on change.")
@click.option("--watch-interval", default=2.0, show_default=True, type=float,
    help="Poll interval in seconds for watch mode.")
@click.option("--link-style", "link_style",
    default="backtick", show_default=True,
    type=click.Choice(["backtick", "wiki"], case_sensitive=False),
    help="Code reference style in docs. 'wiki' uses [[wikilinks]] for a knowledge graph.")
@click.option("--diagrams/--no-diagrams", "embed_diagrams", default=False, show_default=True,
    help=(
        "Generate Mermaid architecture diagrams and embed them in the Architecture chapter. "
        "Also writes diagrams.md alongside the generated docs."
    ))
@click.option("--max-workers", type=int, default=None,
    help="Max parallel chapter generation workers (default: 4).")
@click.option("--model-heavy", default=None,
    help="LLM for heavy-tier chapters (architecture, core-mechanisms). Requires --model auto.")
@click.option("--model-standard", default=None,
    help="LLM for standard-tier chapters (overview, data-models, api-reference). Requires --model auto.")
@click.option("--model-light", default=None,
    help="LLM for light-tier chapters (index, quickstart, dev-guide). Requires --model auto.")
def docs(working_dir, model, api_key, api_base, dry_run, quiet,
         max_files_per_layer,
         output_dir, language, project_name, complexity, theme, do_serve, port, serve_only,
         chunked, do_verify, verify_model, no_verify_docs, facts_only, incremental,
         semantic_dedup, semantic_threshold,
         watch, watch_interval, link_style, embed_diagrams, max_workers,
         model_heavy, model_standard, model_light):
    """
    Generate technical documentation (Docsify-ready, GitHub Pages compatible).

    \b
    Generates up to 8 chapters:
      index.md            Project overview and navigation
      01-overview.md      Tech stack, structure, entry points
      02-quickstart.md    Installation and first run
      03-architecture.md  Architecture and data flow
      04-core-mechanisms.md  Deep dive into key logic
      05-data-models.md   Data structures (if detected)
      06-api-reference.md API endpoints (if detected)
      07-dev-guide.md     Development guide and conventions

    \b
    Also generates Docsify files:
      index.html          Docsify app (works offline, no build step)
      _sidebar.md         Navigation sidebar
      .nojekyll           GitHub Pages compatibility

    \b
    To preview locally:
      python3 -m http.server 8000 --directory docs

    \b
    To publish on GitHub Pages:
      Push to GitHub → Settings → Pages → Source: /docs on main branch

    \b
    Diagram embedding (--diagrams):
      Generates Mermaid diagrams from code analysis and injects them into
      03-architecture.md. Also writes diagrams.md to the output directory.
      Use 'repoforge diagrams' for standalone diagram generation.
    """
    from .docs_generator import generate_docs
    from .server import serve_docs

    if watch:
        from .watch import watch_docs
        watch_docs(
            working_dir=working_dir,
            output_dir=output_dir,
            interval=watch_interval,
            model=model,
            api_key=api_key,
            api_base=api_base,
            language=language,
            project_name=project_name,
            verbose=not quiet,
            complexity=complexity,
            chunked=chunked,
            verify=do_verify,
            verify_model=verify_model,
            no_verify_docs=no_verify_docs,
            facts_only=facts_only,
        )
        return  # watch_docs runs until Ctrl+C

    if not serve_only:
        generate_docs(
            working_dir=working_dir,
            output_dir=output_dir,
            model=model,
            api_key=api_key,
            api_base=api_base,
            language=language,
            project_name=project_name,
            verbose=not quiet,
            dry_run=dry_run,
            complexity=complexity,
            chunked=chunked,
            verify=do_verify,
            verify_model=verify_model,
            no_verify_docs=no_verify_docs,
            facts_only=facts_only,
            incremental=incremental,
            semantic_dedup=semantic_dedup,
            semantic_threshold=semantic_threshold,
            link_style=link_style,
            embed_diagrams=embed_diagrams,
            max_workers=max_workers,
            model_heavy=model_heavy,
            model_standard=model_standard,
            model_light=model_light,
        )

    if do_serve or serve_only:
        # Resolve output_dir relative to working_dir
        from pathlib import Path
        out = Path(output_dir) if Path(output_dir).is_absolute() else Path(working_dir) / output_dir
        serve_docs(str(out), port=port, open_browser=True)


# ---------------------------------------------------------------------------
# export subcommand
# ---------------------------------------------------------------------------

@main.command()
@click.option("-w", "--working-dir",
    default=".", show_default=True,
    help="Path to the repo to analyze.",
    type=click.Path(exists=True, file_okay=False),
)
@click.option("-o", "--output", "output_path", default=None,
    help="Output file path. If not set, prints to stdout.",
    type=click.Path(),
)
@click.option("--max-tokens", default=None, type=int,
    help="Token budget limit. Prioritizes important files first.")
@click.option("--no-contents", is_flag=True, default=False,
    help="Skip file contents — only output tree + definitions.")
@click.option("--format", "fmt",
    default="markdown", show_default=True,
    type=click.Choice(["markdown", "xml"], case_sensitive=False),
    help="Output format: markdown or xml (CXML-style, like rendergit).")
@click.option("--compress", "do_compress", is_flag=True, default=False,
    help="Compress source files to API surface only (signatures, no bodies).")
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def export(working_dir, output_path, max_tokens, no_contents, fmt, do_compress, quiet):
    """
    Flatten a repo into a single LLM-optimized file (no API key needed).

    \b
    Generates a single document with:
      - Project overview (tech stack, entry points)
      - Directory tree
      - Key definitions (functions, classes, constants)
      - Full file contents (respecting token budget)

    \b
    Examples:
      repoforge export -w .                     # print to stdout
      repoforge export -w . -o context.md       # save to file
      repoforge export -w . --max-tokens 100000 # limit output size
      repoforge export -w . --no-contents       # tree + definitions only
      repoforge export -w . --format xml        # XML output (CXML-style)
      repoforge export -w . --compress          # API surface only (60-80% smaller)
    """
    import sys

    from .exporter import export_llm_view

    if not quiet:
        print(f"Exporting LLM view for {working_dir} ...", file=sys.stderr)

    result = export_llm_view(
        workspace=working_dir,
        output_path=output_path,
        max_tokens=max_tokens,
        include_contents=not no_contents,
        fmt=fmt,
        compress=do_compress,
    )

    if output_path:
        if not quiet:
            tokens = len(result) // 4
            print(f"Written to {output_path} (~{tokens:,} tokens)", file=sys.stderr)
    else:
        click.echo(result)


# ---------------------------------------------------------------------------
# score subcommand
# ---------------------------------------------------------------------------

@main.command()
@click.option("-w", "--working-dir",
    default=".", show_default=True,
    help="Path to the repo to analyze.",
    type=click.Path(exists=True, file_okay=False),
)
@click.option("-d", "--skills-dir", default=None,
    help="Skills directory to score. Default: <working-dir>/.claude/skills/",
    type=click.Path(file_okay=False),
)
@click.option("--format", "fmt",
    default="table", show_default=True,
    type=click.Choice(["table", "json", "markdown"], case_sensitive=False),
    help="Output format for the report.")
@click.option("--min-score", default=None, type=float,
    help="Minimum acceptable score (0.0-1.0). Exit code 1 if any skill scores below.")
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def score(working_dir, skills_dir, fmt, min_score, quiet):
    """
    Score quality of generated SKILL.md files (no API key needed).

    \b
    Scans .claude/skills/ for SKILL.md files and scores each across
    7 dimensions: completeness, clarity, specificity, examples,
    format, safety, and agent readiness.

    \b
    Examples:
      repoforge score -w .                     # score with table output
      repoforge score -w . --format json       # JSON output
      repoforge score -w . --min-score 0.7     # fail if any skill < 70%
      repoforge score -d /path/to/skills/      # score specific directory
    """
    import sys
    from pathlib import Path

    from .scorer import SkillScorer

    if skills_dir:
        target = Path(skills_dir)
    else:
        target = Path(working_dir) / ".claude" / "skills"

    if not target.exists():
        click.echo(f"Skills directory not found: {target}", err=True)
        click.echo("Run 'repoforge skills' first to generate skills.", err=True)
        sys.exit(1)

    if not quiet:
        click.echo(f"Scoring skills in {target} ...", err=True)

    scorer = SkillScorer()
    scores = scorer.score_directory(str(target))

    if not scores:
        click.echo("No SKILL.md files found.", err=True)
        sys.exit(1)

    report = scorer.report(scores, fmt=fmt)
    click.echo(report)

    # Exit code 1 if any score below min_score
    if min_score is not None:
        below = [s for s in scores if s.overall < min_score]
        if below:
            if not quiet:
                click.echo(
                    f"\n{len(below)} skill(s) scored below {min_score:.0%} threshold.",
                    err=True,
                )
            sys.exit(1)


# ---------------------------------------------------------------------------
# scan subcommand
# ---------------------------------------------------------------------------

@main.command()
@click.option("-w", "--workspace",
    default=".", show_default=True,
    help="Path to the repo root.",
    type=click.Path(exists=True, file_okay=False),
)
@click.option("--target-dir", default=None,
    help="Specific directory to scan. Default: auto-detect generated output dirs.",
    type=click.Path(file_okay=False),
)
@click.option("--format", "fmt",
    default="table", show_default=True,
    type=click.Choice(["table", "json", "markdown"], case_sensitive=False),
    help="Output format for the report.")
@click.option("--allowlist", default=None,
    help="Comma-separated rule IDs to skip (e.g. SEC-020,SEC-022).")
@click.option("--fail-on",
    default=None,
    type=click.Choice(["critical", "high", "medium", "low"], case_sensitive=False),
    help="Exit code 1 if findings at or above this severity level.")
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def scan(workspace, target_dir, fmt, allowlist, fail_on, quiet):
    """
    Security scan generated output for issues (no API key needed).

    \b
    Scans generated .md files for 5 categories of security issues:
      - Prompt injection patterns
      - Hardcoded secrets (API keys, tokens, passwords)
      - PII exposure (emails, SSNs, phone numbers)
      - Destructive commands (rm -rf /, DROP TABLE, etc.)
      - Unsafe code patterns (eval(), exec(), os.system())

    \b
    Context-aware: patterns inside Anti-Patterns sections are
    downgraded to INFO severity (not false positives).

    \b
    Examples:
      repoforge scan -w .                         # scan with table output
      repoforge scan -w . --format json           # JSON output
      repoforge scan -w . --fail-on critical      # exit 1 on critical findings
      repoforge scan -w . --fail-on high          # exit 1 on high+ findings
      repoforge scan -w . --allowlist SEC-020,SEC-022  # skip email/phone rules
      repoforge scan --target-dir ./my-skills/    # scan specific directory
    """
    import sys
    from pathlib import Path

    from .security import SecurityScanner, Severity, scan_generated_output

    # Parse allowlist
    allow = None
    if allowlist:
        allow = [r.strip() for r in allowlist.split(",") if r.strip()]

    if target_dir:
        target = Path(target_dir)
        if not target.exists():
            click.echo(f"Directory not found: {target}", err=True)
            sys.exit(1)

        if not quiet:
            click.echo(f"Scanning {target} for security issues ...", err=True)

        scanner = SecurityScanner(allowlist=allow)
        result = scanner.scan_directory(str(target))
    else:
        if not quiet:
            click.echo(f"Scanning generated output in {workspace} ...", err=True)

        if allow:
            # Need to create scanner with allowlist and scan manually
            scanner = SecurityScanner(allowlist=allow)
            root = Path(workspace)
            from .security import Finding, ScanResult
            all_findings: list[Finding] = []
            files_scanned = 0

            scan_dirs = [
                root / ".claude" / "skills",
                root / ".claude" / "agents",
                root / ".opencode" / "skills",
                root / ".opencode" / "agents",
            ]
            for scan_dir in scan_dirs:
                if scan_dir.exists():
                    r = scanner.scan_directory(str(scan_dir))
                    all_findings.extend(r.findings)
                    files_scanned += r.files_scanned

            adapter_files = [
                root / "AGENTS.md",
                root / "GEMINI.md",
                root / ".github" / "copilot-instructions.md",
            ]
            for af in adapter_files:
                if af.exists():
                    all_findings.extend(scanner.scan_file(str(af)))
                    files_scanned += 1

            cursor_dir = root / ".cursor" / "rules"
            if cursor_dir.exists():
                r = scanner.scan_directory(str(cursor_dir), extensions=(".mdc",))
                all_findings.extend(r.findings)
                files_scanned += r.files_scanned

            result = ScanResult(files_scanned=files_scanned, findings=all_findings)
        else:
            result = scan_generated_output(workspace)

    # Generate report
    scanner_for_report = SecurityScanner(allowlist=allow)
    report = scanner_for_report.report(result, fmt=fmt)
    click.echo(report)

    # Exit code based on --fail-on
    if fail_on:
        severity_threshold = {
            "critical": [Severity.CRITICAL],
            "high": [Severity.CRITICAL, Severity.HIGH],
            "medium": [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM],
            "low": [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW],
        }
        fail_severities = severity_threshold.get(fail_on, [])
        failing = [f for f in result.findings if f.severity in fail_severities]
        if failing:
            if not quiet:
                click.echo(
                    f"\n{len(failing)} finding(s) at or above '{fail_on}' severity.",
                    err=True,
                )
            sys.exit(1)


# ---------------------------------------------------------------------------
# check subcommand
# ---------------------------------------------------------------------------

@main.command()
@click.option("-w", "--working-dir",
    default=".", show_default=True,
    help="Path to the repo to analyze.",
    type=click.Path(exists=True, file_okay=False),
)
@click.option("--docs-dir", default=None,
    help="Documentation directory to check. Default: <working-dir>/docs/",
    type=click.Path(file_okay=False),
)
@click.option("--format", "fmt",
    default="table", show_default=True,
    type=click.Choice(["table", "json", "markdown"], case_sensitive=False),
    help="Output format for the report.")
@click.option("--fail-on",
    default=None,
    type=click.Choice(["broken", "any"], case_sensitive=False),
    help="Exit code 1 if references of this status are found. "
         "'broken' fails on broken file refs; 'any' includes unresolvable.")
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def check(working_dir, docs_dir, fmt, fail_on, quiet):
    """
    Validate code references in generated documentation (no API key needed).

    \b
    Scans markdown files for code references and checks them against
    the actual codebase:
      - File path references in backticks (e.g., `src/auth.ts`)
      - Symbol references (e.g., `Auth.validate`)

    \b
    Reports: valid refs, broken refs, unresolvable refs.
    Can be used as a CI gate with --fail-on.

    \b
    Examples:
      repoforge check -w .                         # check with table output
      repoforge check -w . --format json           # JSON output
      repoforge check -w . --fail-on broken        # exit 1 on broken refs
      repoforge check -w . --fail-on any           # exit 1 on any issues
      repoforge check -w . --docs-dir my-docs/     # check specific directory
    """
    import sys
    from pathlib import Path

    from .checker import ReferenceChecker, check_docs

    workspace = Path(working_dir).resolve()

    if docs_dir:
        target = Path(docs_dir)
        if not target.is_absolute():
            target = workspace / docs_dir
    else:
        target = workspace / "docs"

    if not target.exists():
        click.echo(f"Documentation directory not found: {target}", err=True)
        click.echo("Run 'repoforge docs' first to generate documentation.", err=True)
        sys.exit(1)

    if not quiet:
        click.echo(f"Checking code references in {target} ...", err=True)

    checker = ReferenceChecker(workspace)
    result = checker.scan_directory(target)

    report = checker.report(result, fmt=fmt)
    click.echo(report)

    if not quiet and result.total_count > 0:
        click.echo(
            f"\nSummary: {result.valid_count} valid, "
            f"{result.broken_count} broken, "
            f"{result.unresolvable_count} unresolvable",
            err=True,
        )

    # Exit code based on --fail-on
    if fail_on:
        if fail_on == "broken" and result.broken_count > 0:
            if not quiet:
                click.echo(
                    f"\n{result.broken_count} broken reference(s) found.",
                    err=True,
                )
            sys.exit(1)
        elif fail_on == "any" and (result.broken_count + result.unresolvable_count) > 0:
            if not quiet:
                click.echo(
                    f"\n{result.broken_count + result.unresolvable_count} "
                    f"problematic reference(s) found.",
                    err=True,
                )
            sys.exit(1)


# ---------------------------------------------------------------------------
# compress subcommand
# ---------------------------------------------------------------------------

@main.command()
@click.option("-w", "--workspace",
    default=".", show_default=True,
    help="Path to the repo root.",
    type=click.Path(exists=True, file_okay=False),
)
@click.option("--target-dir", default=None,
    help="Specific directory to compress. Default: <workspace>/.claude/skills/",
    type=click.Path(file_okay=False),
)
@click.option("--aggressive", is_flag=True, default=False,
    help="Use abbreviations (function→fn, configuration→config, etc.).")
@click.option("--dry-run", is_flag=True, default=False,
    help="Show compression stats without modifying files.")
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def compress(workspace, target_dir, aggressive, dry_run, quiet):
    """
    Token-optimize generated .md files (no API key needed).

    \b
    Applies deterministic multi-pass compression to reduce token count
    by ~50-75% while preserving all semantic information:
      - Whitespace normalization
      - Filler phrase removal
      - Table compaction
      - Code block cleanup
      - Bullet consolidation
      - Abbreviations (--aggressive only)

    \b
    Examples:
      repoforge compress -w .                       # compress .claude/skills/
      repoforge compress -w . --aggressive           # also abbreviate words
      repoforge compress -w . --dry-run              # show stats only
      repoforge compress --target-dir ./my-skills/   # compress specific dir
    """
    import sys
    from pathlib import Path

    from .compressor import (
        SkillCompressor,
        compress_directory,
        compression_report,
    )

    if target_dir:
        target = Path(target_dir)
    else:
        target = Path(workspace) / ".claude" / "skills"

    if not target.exists():
        click.echo(f"Directory not found: {target}", err=True)
        click.echo("Run 'repoforge skills' first to generate skills.", err=True)
        sys.exit(1)

    if not quiet:
        mode = "aggressive" if aggressive else "normal"
        click.echo(f"Compressing .md files in {target} (mode={mode}) ...", err=True)

    if dry_run:
        # Dry-run: compute stats without writing
        compressor = SkillCompressor()
        results = []
        for md_file in sorted(target.rglob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            result = compressor.compress(content, aggressive=aggressive)
            results.append(result)
            if not quiet:
                pct = (1.0 - result.ratio) * 100 if result.ratio < 1.0 else 0.0
                try:
                    rel = str(md_file.relative_to(target))
                except ValueError:
                    rel = md_file.name
                click.echo(
                    f"  {rel}: {result.original_tokens} → {result.compressed_tokens} "
                    f"tokens ({pct:.1f}% reduction)",
                    err=True,
                )
    else:
        results = compress_directory(str(target), aggressive=aggressive)

    if results:
        report = compression_report(results)
        click.echo(report)
    else:
        click.echo("No .md files found.", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# graph subcommand
# ---------------------------------------------------------------------------

@main.command()
@click.option("-w", "--workspace",
    default=".", show_default=True,
    help="Path to the repo root.",
    type=click.Path(exists=True, file_okay=False),
)
@click.option("-o", "--output", "output_path", default=None,
    help="Output file path. If not set, prints to stdout.",
    type=click.Path(),
)
@click.option("--format", "fmt",
    default="summary", show_default=True,
    type=click.Choice(["mermaid", "json", "dot", "summary"], case_sensitive=False),
    help="Output format: mermaid, json, dot, or summary.")
@click.option("--type", "graph_type",
    default="deps", show_default=True,
    type=click.Choice(["deps", "calls"], case_sensitive=False),
    help="Graph type: deps (file-level dependencies) or calls (symbol-level call graph).")
@click.option("--blast-radius", default=None,
    help="Show blast radius for a specific module (path or name).")
@click.option("--v2", is_flag=True, default=False,
    help="Use extractor-based graph builder (file-level dependencies).")
@click.option("--depth", default=3, show_default=True, type=int,
    help="Max BFS depth for blast radius (v2 only).")
@click.option("--max-files", default=50, show_default=True, type=int,
    help="Max files in blast radius result (v2 only).")
@click.option("--include-tests/--no-include-tests", default=True, show_default=True,
    help="Include test files in blast radius (v2 only).")
@click.option("--query", "query_mode", default=None,
    type=click.Choice(["callers", "callees", "imports"], case_sensitive=False),
    help="Query mode: callers (who calls symbol), callees (what symbol calls), imports (file imports).")
@click.option("--symbol", default=None,
    help="Symbol name for --query callers/callees.")
@click.option("--file", "query_file", default=None,
    help="File path for --query imports.")
@click.option("--communities", is_flag=True, default=False,
    help="Detect and display module communities (clusters of related modules).")
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def graph(workspace, output_path, fmt, graph_type, blast_radius, v2, depth, max_files, include_tests, query_mode, symbol, query_file, communities, quiet):
    """
    Build a code knowledge graph from scanner data (no API key needed).

    \b
    Scans the repo and builds a lightweight dependency graph based on
    import/export name matching. No tree-sitter needed — uses RepoMap data.

    \b
    Graph types:
      deps   — File-level dependency graph (default)
      calls  — Symbol-level call graph (function-to-function)

    \b
    Output formats:
      summary  — Human-readable stats (modules, deps, most connected)
      mermaid  — Mermaid flowchart diagram (for docs / README)
      json     — D3/Cytoscape-compatible nodes + edges
      dot      — Graphviz DOT format (deps only)

    \b
    Examples:
      repoforge graph -w .                             # summary to stdout
      repoforge graph -w . --format mermaid            # Mermaid diagram
      repoforge graph -w . --format json -o graph.json # JSON to file
      repoforge graph -w . --format dot -o graph.dot   # DOT to file
      repoforge graph -w . --blast-radius src/auth.py  # blast radius
      repoforge graph -w . --type calls                # symbol call graph
      repoforge graph -w . --type calls --format json  # call graph as JSON
      repoforge graph --query callers --symbol build_graph  # who calls this?
      repoforge graph --query callees --symbol main         # what does it call?
      repoforge graph --query imports --file repoforge/cli.py  # file imports
    """
    import sys

    # --- Query mode: structured queries for external tools ---
    if query_mode:
        if query_mode in ("callers", "callees"):
            if not symbol:
                click.echo(
                    f"Error: --query {query_mode} requires --symbol <name>.",
                    err=True,
                )
                sys.exit(1)

            if not quiet:
                print(
                    f"Querying {query_mode} for symbol '{symbol}' in {workspace} ...",
                    file=sys.stderr,
                )

            from .graph_query import query_callees, query_callers
            from .symbols import build_symbol_graph

            sym_graph = build_symbol_graph(workspace)

            if query_mode == "callers":
                result = query_callers(sym_graph, symbol)
            else:
                result = query_callees(sym_graph, symbol)

            output = result.to_json()

        elif query_mode == "imports":
            if not query_file:
                click.echo(
                    "Error: --query imports requires --file <path>.",
                    err=True,
                )
                sys.exit(1)

            if not quiet:
                print(
                    f"Querying imports for '{query_file}' in {workspace} ...",
                    file=sys.stderr,
                )

            from .graph import build_graph_v2
            from .graph_query import query_imports

            code_graph = build_graph_v2(workspace)
            result = query_imports(code_graph, query_file)
            output = result.to_json()

        # Write query output
        if output_path:
            from pathlib import Path
            Path(output_path).write_text(output, encoding="utf-8")
            if not quiet:
                print(f"Written to {output_path}", file=sys.stderr)
        else:
            click.echo(output)
        return

    # --- Calls mode: symbol-level call graph ---
    if graph_type == "calls":
        if blast_radius:
            click.echo(
                "Error: --blast-radius is not supported with --type calls "
                "(blast radius operates on file-level graphs).",
                err=True,
            )
            sys.exit(1)

        if not quiet:
            print(f"Building symbol call graph for {workspace} ...", file=sys.stderr)

        from .symbols import build_symbol_graph, render_symbol_mermaid

        sym_graph = build_symbol_graph(workspace)

        if fmt == "mermaid":
            output = render_symbol_mermaid(sym_graph)
        elif fmt == "json":
            output = sym_graph.to_json()
        elif fmt == "dot":
            click.echo("DOT format is not supported for call graphs. Use mermaid, json, or summary.", err=True)
            sys.exit(1)
        else:
            output = sym_graph.summary()

    # --- Deps mode: file-level dependency graph (default) ---
    else:
        if not quiet:
            mode = "v2 (extractor-based)" if v2 else "v1 (name-matching)"
            print(f"Building code graph for {workspace} ({mode}) ...", file=sys.stderr)

        if v2:
            from .graph import build_graph_v2
            code_graph = build_graph_v2(workspace)
        else:
            from .graph import build_graph_from_workspace
            code_graph = build_graph_from_workspace(workspace)

        # Handle blast radius mode
        if blast_radius:
            # Try exact match first, then fuzzy match on module name
            node = code_graph.get_node(blast_radius)
            if not node:
                # Search by name or partial path
                for n in code_graph.nodes:
                    if n.name == blast_radius or blast_radius in n.id:
                        node = n
                        break

            if not node:
                click.echo(f"Module not found: {blast_radius}", err=True)
                click.echo("Available modules:", err=True)
                for n in code_graph.nodes:
                    if n.node_type == "module":
                        click.echo(f"  {n.id} ({n.name})", err=True)
                sys.exit(1)

            if v2:
                from .graph import get_blast_radius_v2
                br = get_blast_radius_v2(
                    code_graph, node.id,
                    max_depth=depth, max_files=max_files,
                    include_tests=include_tests,
                )
                lines = [
                    f"Blast radius for: {node.id}",
                    f"Directly depends on: {', '.join(code_graph.get_dependencies(node.id)) or 'nothing'}",
                    f"Direct dependents: {', '.join(code_graph.get_dependents(node.id)) or 'none'}",
                    f"Affected files: {len(br.files)}",
                    f"Test files: {len(br.test_files)}",
                    f"Max depth reached: {br.depth}",
                    f"Exceeded cap: {br.exceeded_cap}",
                ]
                if br.files:
                    lines.append("")
                    lines.append("Affected files:")
                    for fid in br.files:
                        anode = code_graph.get_node(fid)
                        name = anode.name if anode else fid
                        lines.append(f"  {name} ({fid})")
                if br.test_files:
                    lines.append("")
                    lines.append("Related test files:")
                    for fid in br.test_files:
                        lines.append(f"  {fid}")
            else:
                affected = code_graph.get_blast_radius(node.id)
                lines = [
                    f"Blast radius for: {node.id}",
                    f"Directly depends on: {', '.join(code_graph.get_dependencies(node.id)) or 'nothing'}",
                    f"Direct dependents: {', '.join(code_graph.get_dependents(node.id)) or 'none'}",
                    f"Total affected by change: {len(affected)} module(s)",
                ]
                if affected:
                    lines.append("")
                    lines.append("Affected modules:")
                    for mid in affected:
                        anode = code_graph.get_node(mid)
                        name = anode.name if anode else mid
                        lines.append(f"  {name} ({mid})")

            output = "\n".join(lines)
        else:
            # Run community detection if requested
            if communities:
                from .graph import assign_communities, detect_communities
                comm = detect_communities(code_graph)
                assign_communities(code_graph, comm)

            # Normal format output
            if fmt == "mermaid":
                if communities:
                    output = _mermaid_with_communities(code_graph, comm)
                else:
                    output = code_graph.to_mermaid()
            elif fmt == "json":
                output = code_graph.to_json()
            elif fmt == "dot":
                output = code_graph.to_dot()
            else:
                base = code_graph.summary()
                if communities:
                    base += "\n\n" + _format_community_summary(comm)
                output = base

    # Write output
    if output_path:
        from pathlib import Path
        Path(output_path).write_text(output, encoding="utf-8")
        if not quiet:
            print(f"Written to {output_path}", file=sys.stderr)
    else:
        click.echo(output)


def _format_community_summary(communities: dict[str, list[str]]) -> str:
    """Format communities as a human-readable summary block."""
    from pathlib import Path
    lines = [f"Communities: {len(communities)}"]
    for cname, members in sorted(communities.items()):
        sample = ", ".join(Path(f).name for f in members[:5])
        suffix = f" +{len(members) - 5} more" if len(members) > 5 else ""
        lines.append(f"  {cname} ({len(members)} modules): {sample}{suffix}")
    return "\n".join(lines)


def _mermaid_with_communities(graph, communities: dict[str, list[str]]) -> str:
    """Render mermaid diagram with community subgraphs instead of layers."""
    import re
    lines = ["graph LR"]

    module_nodes = [n for n in graph.nodes if n.node_type == "module"]
    if len(module_nodes) > 50:
        module_nodes = module_nodes[:50]
    visible_ids = {n.id for n in module_nodes}

    # Map node → community
    node_community: dict[str, str] = {}
    for cname, members in communities.items():
        for nid in members:
            if nid in visible_ids:
                node_community[nid] = cname

    # Group by community
    by_community: dict[str, list] = {}
    for n in module_nodes:
        cname = node_community.get(n.id, "uncategorized")
        by_community.setdefault(cname, []).append(n)

    for cname, cnodes in sorted(by_community.items()):
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", cname)
        lines.append(f"    subgraph {safe_name}")
        for n in cnodes:
            safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", n.id)
            safe_label = re.sub(r"[\"'\\[\\]{}|<>]", "", n.name)
            lines.append(f"        {safe_id}[{safe_label}]")
        lines.append("    end")

    for e in graph.edges:
        if e.edge_type == "contains":
            continue
        if e.source in visible_ids and e.target in visible_ids:
            src = re.sub(r"[^a-zA-Z0-9_]", "_", e.source)
            tgt = re.sub(r"[^a-zA-Z0-9_]", "_", e.target)
            lines.append(f"    {src} --> {tgt}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# diff subcommand
# ---------------------------------------------------------------------------

@main.command()
@click.argument("ref_a")
@click.argument("ref_b")
@click.option("-w", "--workspace",
    default=".", show_default=True,
    help="Path to the repo root.",
    type=click.Path(exists=True, file_okay=False),
)
@click.option("--format", "fmt",
    default="table", show_default=True,
    type=click.Choice(["table", "json", "markdown"], case_sensitive=False),
    help="Output format.")
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def diff(ref_a, ref_b, workspace, fmt, quiet):
    """
    Entity-level semantic diff between two git refs (no API key needed).

    \b
    Shows which functions/classes were added, removed, modified (cosmetic
    vs logic change), or renamed between REF_A and REF_B.

    \b
    Examples:
      repoforge diff HEAD~1 HEAD
      repoforge diff main feature-branch --format json
      repoforge diff v1.0.0 v2.0.0 --format markdown
    """
    from .diff import diff_entities, render_diff_json, render_diff_markdown, render_diff_table

    if not quiet:
        click.echo(f"Computing entity diff: {ref_a} → {ref_b} ...", err=True)

    try:
        result = diff_entities(workspace, ref_a, ref_b)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)

    if fmt == "json":
        output = render_diff_json(result)
    elif fmt == "markdown":
        output = render_diff_markdown(result)
    else:
        output = render_diff_table(result)

    click.echo(output)

    if not quiet and result.entries:
        s = result.summary
        click.echo(
            f"\n{s['total']} entities changed: "
            f"{s['added']} added, {s['removed']} removed, "
            f"{s['modified']} modified, {s['renamed']} renamed",
            err=True,
        )



# ---------------------------------------------------------------------------
# audit subcommand
# ---------------------------------------------------------------------------

@main.command()
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option("--fail-on",
    default="high", show_default=True,
    type=click.Choice(["none", "medium", "high"], case_sensitive=False),
    help=(
        "Exit code 1 threshold. high: only on high-severity findings. "
        "medium: on medium+ findings. none: always exit 0."
    ),
)
@click.option("--fmt", "--format", "fmt",
    default="text", show_default=True,
    type=click.Choice(["text", "json"], case_sensitive=False),
    help="Output format: text (human-readable) or json (structured).",
)
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output (only print findings).",
)
def audit(path, fail_on, fmt, quiet):
    """
    Run all analysis checks in one shot (no API key needed).

    \b
    Runs four analysis steps and aggregates findings:
      1. Complexity   -- cyclomatic complexity per function
      2. Dead Code    -- functions never referenced elsewhere
      3. Doc Drift    -- docs stale relative to source
      4. Dep Health   -- dependency duplicates, outdated, license conflicts

    \b
    Exit codes:
      0 -- no findings above threshold (or --fail-on none)
      1 -- findings at or above the --fail-on severity level

    \b
    Examples:
      repoforge audit .
      repoforge audit . --fail-on medium
      repoforge audit . --fmt json
      repoforge audit . --fail-on none --fmt json
      repoforge audit /path/to/repo --quiet
    """
    import json as _json
    import sys
    from pathlib import Path

    from .analysis import analyze_complexity, detect_dead_code
    from .ci import detect_doc_drift
    from .dep_health import analyze_dependency_health

    root = Path(path).resolve()

    if not quiet:
        click.echo(f"Auditing {root} ...", err=True)

    try:
        from .scanner import scan_repo
        repo_map = scan_repo(str(root))
        all_files = [
            m["path"]
            for layer in repo_map["layers"].values()
            for m in layer.get("modules", [])
        ]
    except Exception:
        all_files = [
            str(p.relative_to(root))
            for p in root.rglob("*.py")
            if ".git" not in p.parts
        ]

    _COMPLEXITY_HIGH = 15
    _COMPLEXITY_MEDIUM = 10

    file_contents: dict[str, str] = {}
    for f in all_files[:200]:
        p = root / f
        if p.is_file():
            try:
                file_contents[f] = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass

    complexity_report = analyze_complexity(file_contents)

    complexity_findings: list[dict] = []
    for mod in complexity_report.modules:
        if mod.max_complexity >= _COMPLEXITY_HIGH:
            severity = "high"
        elif mod.max_complexity >= _COMPLEXITY_MEDIUM:
            severity = "medium"
        else:
            continue
        complexity_findings.append({
            "type": "complexity",
            "severity": severity,
            "file": mod.file,
            "function": mod.most_complex,
            "value": int(mod.max_complexity),
            "threshold": _COMPLEXITY_HIGH if severity == "high" else _COMPLEXITY_MEDIUM,
            "message": (
                f"{mod.file}:{mod.most_complex}() -- cyclomatic complexity: "
                f"{int(mod.max_complexity)} (threshold: "
                f"{_COMPLEXITY_HIGH if severity == 'high' else _COMPLEXITY_MEDIUM})"
            ),
        })

    dead_findings: list[dict] = []
    try:
        from .intelligence.doc_chunks import build_all_ast_symbols
        ast_symbols = build_all_ast_symbols(str(root), all_files)
        dead_report = detect_dead_code(ast_symbols)
        for sym in dead_report.unreferenced:
            dead_findings.append({
                "type": "dead_code",
                "severity": "medium",
                "file": sym.file,
                "symbol": sym.name,
                "line": sym.line,
                "message": f"{sym.file}:{sym.name} -- never referenced",
            })
    except Exception as exc:
        if not quiet:
            click.echo(f"  [dead code] skipped: {exc}", err=True)

    drift_findings: list[dict] = []
    docs_dir = root / "docs"
    if docs_dir.exists():
        try:
            drift_report = detect_doc_drift(root, docs_dir=docs_dir)
            if drift_report.is_stale:
                drift_findings.append({
                    "type": "doc_drift",
                    "severity": "medium",
                    "file": "docs/",
                    "message": "docs/ -- source changed, docs stale",
                })
        except Exception as exc:
            if not quiet:
                click.echo(f"  [doc drift] skipped: {exc}", err=True)

    dep_findings: list[dict] = []
    try:
        dep_report = analyze_dependency_health(str(root))
        if dep_report is not None:
            for dup in dep_report.duplicates:
                dep_findings.append({
                    "type": "dep_health",
                    "severity": "medium",
                    "package": dup.name,
                    "versions": dup.versions,
                    "message": (
                        f"{dup.name} -- duplicate versions: "
                        f"{', '.join(dup.versions[:5])}"
                    ),
                })
            for lc in dep_report.license_conflicts:
                dep_findings.append({
                    "type": "dep_health",
                    "severity": "high",
                    "package": lc.package,
                    "license": lc.license,
                    "message": f"{lc.package} -- {lc.reason}",
                })
    except Exception as exc:
        if not quiet:
            click.echo(f"  [dep health] skipped: {exc}", err=True)

    all_findings = complexity_findings + dead_findings + drift_findings + dep_findings

    high_count = sum(1 for f in all_findings if f["severity"] == "high")
    medium_count = sum(1 for f in all_findings if f["severity"] == "medium")
    total_count = len(all_findings)

    if fmt == "json":
        output = _json.dumps({
            "path": str(root),
            "summary": {
                "total": total_count,
                "high": high_count,
                "medium": medium_count,
            },
            "findings": {
                "complexity": complexity_findings,
                "dead_code": dead_findings,
                "doc_drift": drift_findings,
                "dep_health": dep_findings,
            },
        }, indent=2)
        click.echo(output)
    else:
        lines: list[str] = []

        lines.append("\n=== Complexity ===")
        if complexity_findings:
            for f in complexity_findings:
                icon = "x" if f["severity"] == "high" else "!"
                lines.append(f"  {icon} {f['message']}")
        else:
            lines.append("  ok no issues")

        lines.append("\n=== Dead Code ===")
        if dead_findings:
            for f in dead_findings:
                lines.append(f"  x {f['message']}")
        else:
            lines.append("  ok no issues")

        lines.append("\n=== Doc Drift ===")
        if drift_findings:
            for f in drift_findings:
                lines.append(f"  x {f['message']}")
        elif not docs_dir.exists():
            lines.append("  - docs/ not found, skipped")
        else:
            lines.append("  ok docs up to date")

        lines.append("\n=== Dep Health ===")
        if dep_findings:
            for f in dep_findings:
                icon = "x" if f["severity"] == "high" else "!"
                lines.append(f"  {icon} {f['message']}")
        else:
            lines.append("  ok no issues")

        if total_count == 0:
            summary_line = "\n=== Summary ===\n  0 findings -- exit 0"
        else:
            parts = []
            if high_count:
                parts.append(f"{high_count} high")
            if medium_count:
                parts.append(f"{medium_count} medium")
            breakdown = ", ".join(parts)
            threshold_map = {
                "high": "exit 1 (high findings present)",
                "medium": "exit 1 (medium+ findings present)",
                "none": "exit 0 (--fail-on none)",
            }
            threshold_label = threshold_map.get(fail_on.lower(), "")
            summary_line = (
                f"\n=== Summary ===\n"
                f"  {total_count} finding(s) ({breakdown}) -- {threshold_label}"
            )
        lines.append(summary_line)

        click.echo("\n".join(lines))

    if fail_on.lower() == "none":
        sys.exit(0)

    should_fail = False
    if fail_on.lower() == "high" and high_count > 0:
        should_fail = True
    elif fail_on.lower() == "medium" and (high_count + medium_count) > 0:
        should_fail = True

    if should_fail:
        sys.exit(1)

# ---------------------------------------------------------------------------
# diagram subcommand
# ---------------------------------------------------------------------------

@main.command()
@click.option("-w", "--workspace",
    default=".", show_default=True,
    help="Path to the repo root.",
    type=click.Path(exists=True, file_okay=False),
)
@click.option("-o", "--output", "output_path", default=None,
    help="Output file path. If not set, prints to stdout.",
    type=click.Path(),
)
@click.option("--type", "diagram_type",
    default="all", show_default=True,
    type=click.Choice(["dependency", "directory", "callflow", "erd", "k8s", "openapi", "all"], case_sensitive=False),
    help="Diagram type to generate.")
@click.option("--max-nodes", default=40, show_default=True, type=int,
    help="Max nodes in dependency diagram.")
@click.option("--max-depth", default=3, show_default=True, type=int,
    help="Max depth for directory/call flow diagrams.")
@click.option("--entry", default=None,
    help="Entry point file for call flow diagram (auto-detected if not set).")
@click.option("--input", "input_path", default=None,
    help="Input file for erd/k8s/openapi diagram types.",
    type=click.Path(exists=True, dir_okay=False),
)
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def diagram(workspace, output_path, diagram_type, max_nodes, max_depth, entry, input_path, quiet):
    """
    Generate Mermaid architecture diagrams from code analysis (no API key needed).

    \b
    Analyzes imports/exports and project structure to produce Mermaid diagrams
    suitable for embedding in documentation or README files.

    \b
    Diagram types:
      dependency  — Module dependency flowchart (imports/exports)
      directory   — Project directory hierarchy
      callflow    — Sequence diagram from entry point call chains
      erd         — Entity-Relationship from SQL CREATE TABLE (requires --input)
      k8s         — Kubernetes resource graph from YAML manifests (requires --input)
      openapi     — API structure from OpenAPI/Swagger spec (requires --input)
      all         — All diagram types combined

    \b
    Examples:
      repoforge diagram -w .                          # all diagrams to stdout
      repoforge diagram -w . --type dependency        # dependency graph only
      repoforge diagram -w . --type callflow --entry src/main.py
      repoforge diagram -w . --type erd --input schema.sql
      repoforge diagram -w . --type k8s --input k8s/deployment.yaml
      repoforge diagram -w . --type openapi --input openapi.json
      repoforge diagram -w . -o diagrams.md           # save to file
    """
    import sys
    from pathlib import Path

    if not quiet:
        print(f"Generating {diagram_type} diagram(s) for {workspace} ...", file=sys.stderr)

    from .diagrams import (
        generate_all_diagrams,
        generate_call_flow_diagram,
        generate_dependency_diagram,
        generate_directory_diagram,
        generate_erd_diagram,
        generate_k8s_diagram,
        generate_openapi_diagram,
    )
    from .graph import build_graph_v2
    from .ripgrep import list_files

    root = Path(workspace).resolve()
    code_graph = build_graph_v2(str(root))

    # Discover files
    discovered = list_files(root)
    files = []
    for f in discovered:
        try:
            files.append(str(f.relative_to(root)))
        except ValueError:
            pass

    if diagram_type == "all":
        output = generate_all_diagrams(
            str(root), code_graph, files,
            max_dep_nodes=max_nodes, max_dir_depth=max_depth,
            max_call_depth=max_depth,
        )
    elif diagram_type == "dependency":
        mermaid = generate_dependency_diagram(code_graph, max_nodes=max_nodes)
        output = "```mermaid\n" + mermaid + "\n```"
    elif diagram_type == "directory":
        mermaid = generate_directory_diagram(files, max_depth=max_depth)
        output = "```mermaid\n" + mermaid + "\n```"
    elif diagram_type == "callflow":
        if not entry:
            from .diagrams import _detect_entry_points
            entries = _detect_entry_points(str(root), files)
            if not entries:
                click.echo("No entry point detected. Use --entry to specify one.", err=True)
                sys.exit(1)
            entry = entries[0]
            if not quiet:
                print(f"Auto-detected entry point: {entry}", file=sys.stderr)
        mermaid = generate_call_flow_diagram(
            str(root), entry, files, max_depth=max_depth,
        )
        output = "```mermaid\n" + mermaid + "\n```"
    elif diagram_type in ("erd", "k8s", "openapi"):
        if not input_path:
            click.echo(f"--input is required for --type {diagram_type}.", err=True)
            sys.exit(1)
        content = Path(input_path).read_text(encoding="utf-8")
        if diagram_type == "erd":
            mermaid = generate_erd_diagram(content)
        elif diagram_type == "k8s":
            mermaid = generate_k8s_diagram(content)
        else:
            mermaid = generate_openapi_diagram(content)
        output = "```mermaid\n" + mermaid + "\n```"
    else:
        output = ""

    # Write output
    if output_path:
        Path(output_path).write_text(output, encoding="utf-8")
        if not quiet:
            print(f"Written to {output_path}", file=sys.stderr)
    else:
        click.echo(output)


# ---------------------------------------------------------------------------
# diagrams subcommand (plural) — generates all 3 diagram types to a .md file
# ---------------------------------------------------------------------------

@main.command(name="diagrams")
@click.option("-w", "--workspace",
    default=".", show_default=True,
    help="Path to the repo root.",
    type=click.Path(exists=True, file_okay=False),
)
@click.option("-o", "--output",
    default="diagrams.md", show_default=True,
    help="Output markdown file path.",
    type=click.Path(),
)
@click.option("--max-nodes", default=40, show_default=True, type=int,
    help="Max nodes in dependency diagram.")
@click.option("--max-depth", default=3, show_default=True, type=int,
    help="Max depth for directory/call flow diagrams.")
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def diagrams_cmd(workspace, output, max_nodes, max_depth, quiet):
    """
    Generate all Mermaid architecture diagrams to a combined markdown file.

    \b
    Produces three diagram types:
      dependency  — Module dependency flowchart (imports/exports)
      directory   — Project directory hierarchy
      callflow    — Sequence diagram from entry point call chains

    \b
    Output is a single markdown file with fenced ```mermaid blocks,
    ready to embed in documentation or README files.

    \b
    Examples:
      repoforge diagrams -w .                   # writes diagrams.md
      repoforge diagrams -w . -o docs/arch.md   # custom output path
      repoforge diagrams -w . --max-nodes 60    # larger dependency graph
    """
    import sys
    from pathlib import Path

    root = Path(workspace).resolve()

    if not quiet:
        print(f"Generating all diagrams for {workspace} ...", file=sys.stderr)

    from .diagrams import generate_all_diagrams
    from .graph import build_graph_v2
    from .ripgrep import list_files

    try:
        code_graph = build_graph_v2(str(root))
    except (ImportError, OSError, ValueError, RuntimeError) as e:
        click.echo(f"Error building dependency graph: {e}", err=True)
        sys.exit(1)

    files = list_files(str(root))
    try:
        files = [str(Path(f).relative_to(root)) for f in files]
    except ValueError:
        pass

    content = generate_all_diagrams(
        str(root), code_graph, files,
        max_dep_nodes=max_nodes, max_dir_depth=max_depth,
        max_call_depth=max_depth,
    )

    # Add a header
    project_name = root.name.replace("-", " ").replace("_", " ").title()
    header = f"# {project_name} — Architecture Diagrams\n\n"
    header += "_Auto-generated by [RepoForge](https://github.com/your/repoforge). Do not edit manually._\n\n"
    full_output = header + content

    out_path = Path(output) if Path(output).is_absolute() else Path.cwd() / output
    out_path.write_text(full_output, encoding="utf-8")

    if not quiet:
        print(f"Written to {out_path}", file=sys.stderr)
        print(f"Sections: {full_output.count('```mermaid')} diagram(s)", file=sys.stderr)


# ---------------------------------------------------------------------------
# import-docs subcommand
# ---------------------------------------------------------------------------

@main.command(name="import-docs")
@click.option("-w", "--working-dir",
    default=".", show_default=True,
    help="Path to the repo root.",
    type=click.Path(exists=True, file_okay=False),
)
@click.option("--npm", multiple=True,
    help="npm package name to fetch README for. Repeatable.")
@click.option("--pypi", multiple=True,
    help="PyPI package name to fetch description for. Repeatable.")
@click.option("--github", multiple=True,
    help="GitHub repo URL to clone and extract docs from. Repeatable.")
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def import_docs_cmd(working_dir, npm, pypi, github, quiet):
    """
    Import external dependency docs to enrich analysis context.

    \b
    Fetches documentation from package registries and repositories,
    saving them as flat markdown in .repoforge/external-docs/.

    \b
    No API key needed — pure HTTP fetching.

    \b
    Examples:
      repoforge import-docs --npm react --npm express
      repoforge import-docs --pypi click --pypi pyyaml
      repoforge import-docs --github https://github.com/pallets/click
      repoforge import-docs --npm react --pypi flask -w /my/repo
    """
    import sys

    from .import_docs import import_docs

    if not npm and not pypi and not github:
        click.echo(
            "Error: at least one of --npm, --pypi, or --github is required.",
            err=True,
        )
        sys.exit(1)

    if not quiet:
        total = len(npm) + len(pypi) + len(github)
        click.echo(f"Importing docs for {total} source(s)...", err=True)

    result = import_docs(
        working_dir=working_dir,
        npm=list(npm),
        pypi=list(pypi),
        github=list(github),
        quiet=quiet,
    )

    if not quiet:
        click.echo(f"  Imported: {result['total']} doc(s)", err=True)
        if result["failed"]:
            click.echo(f"  Failed:   {len(result['failed'])} source(s)", err=True)
            for f in result["failed"]:
                click.echo(f"    - {f['source']}: {f['error']}", err=True)
        click.echo(f"  Output:   {result['output_dir']}", err=True)

    if result["failed"] and not result["imported"]:
        sys.exit(1)


# ---------------------------------------------------------------------------
# skills-from-docs subcommand
# ---------------------------------------------------------------------------

@main.command(name="skills-from-docs")
@click.option("-w", "--source",
    required=True,
    help="Documentation source: URL, GitHub repo URL, or local directory path.")
@click.option("-o", "--output-dir", default=".claude/skills", show_default=True,
    help="Output directory for generated SKILL.md.")
@click.option("--name", default=None,
    help="Skill name (kebab-case). Auto-derived from docs title if not set.")
@click.option("--dry-run", is_flag=True, default=False,
    help="Show what would be generated without writing files.")
@click.option("--score/--no-score", "do_score", default=False, show_default=True,
    help="After generation, score quality of the generated SKILL.md.")
@click.option("--check-conflicts/--no-check-conflicts", "do_conflicts", default=True, show_default=True,
    help="Compare against existing skills and warn on contradictions.")
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def skills_from_docs(source, output_dir, name, dry_run, do_score, do_conflicts, quiet):
    """
    Generate SKILL.md from documentation (URL, GitHub repo, local dir, PDF, YouTube, notebook).

    \b
    Accepts six types of sources:
      - HTTP/HTTPS URL: scrapes documentation page
      - GitHub repo URL: clones and scans .md files
      - Local directory: reads .md/.html files recursively
      - PDF file (.pdf): extracts text (requires: pip install repoforge[pdf])
      - YouTube URL: downloads transcript (requires: pip install repoforge[youtube])
      - Jupyter notebook (.ipynb): parses markdown + code cells

    \b
    No API key needed — extraction and generation are deterministic.

    \b
    Examples:
      repoforge skills-from-docs -w https://docs.example.com/guide
      repoforge skills-from-docs -w https://github.com/org/repo -o .claude/skills
      repoforge skills-from-docs -w /path/to/docs --name my-lib
      repoforge skills-from-docs -w /path/to/docs --dry-run
      repoforge skills-from-docs -w /path/to/docs --score
      repoforge skills-from-docs -w /path/to/guide.pdf --name my-lib
      repoforge skills-from-docs -w https://youtube.com/watch?v=VIDEO_ID
      repoforge skills-from-docs -w /path/to/notebook.ipynb
    """
    import sys
    from pathlib import Path

    from .skills_from_docs import (
        check_conflicts,
        extract_content,
        generate_skill_md,
        ingest,
    )

    # Step 1: Ingest
    if not quiet:
        click.echo(f"Ingesting documentation from: {source}", err=True)

    try:
        raw_texts = ingest(source)
    except (ValueError, RuntimeError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if not quiet:
        click.echo(f"  Fetched {len(raw_texts)} document(s)", err=True)

    # Step 2: Extract
    if not quiet:
        click.echo("Extracting content...", err=True)

    doc = extract_content(raw_texts, source=source)

    if not quiet:
        click.echo(
            f"  Title: {doc.title}\n"
            f"  Sections: {len(doc.sections)}\n"
            f"  Code examples: {len(doc.code_examples)}\n"
            f"  Patterns: {len(doc.patterns)}\n"
            f"  Anti-patterns: {len(doc.anti_patterns)}",
            err=True,
        )

    # Step 3: Generate
    if not quiet:
        click.echo("Generating SKILL.md...", err=True)

    skill_md = generate_skill_md(doc, name=name)

    if dry_run:
        click.echo("\n--- Generated SKILL.md (dry run) ---\n")
        click.echo(skill_md)
        return

    # Step 4: Write
    out_path = Path(output_dir)
    skill_name = name or doc.title.lower().replace(" ", "-")
    skill_dir = out_path / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(skill_md, encoding="utf-8")

    if not quiet:
        click.echo(f"  Written to: {skill_file}", err=True)

    # Step 5: Conflict check
    if do_conflicts:
        conflicts = check_conflicts(skill_md, str(out_path))
        if conflicts:
            click.echo(f"\n⚠️  Found {len(conflicts)} potential conflict(s):", err=True)
            for c in conflicts:
                click.echo(f"  - {c.description}", err=True)
        elif not quiet:
            click.echo("  No conflicts with existing skills.", err=True)

    # Step 6: Optional scoring
    if do_score:
        from .scorer import SkillScorer
        scorer = SkillScorer()
        scores = scorer.score_directory(str(skill_dir))
        if scores:
            click.echo(scorer.report(scores, fmt="table"), err=True)

    if not quiet:
        click.echo(f"\n✅ SKILL.md generated: {skill_file}", err=True)


# ---------------------------------------------------------------------------
# prompts subcommand
# ---------------------------------------------------------------------------

@main.command()
@click.option("-w", "--working-dir",
    default=".", show_default=True,
    help="Path to the repo to analyze.",
    type=click.Path(exists=True, file_okay=False),
)
@click.option("-o", "--output-dir", "output_dir", default=None,
    help="Output directory. Writes individual .txt per prompt. If not set, prints single markdown to stdout.",
    type=click.Path(),
)
@click.option("--type", "prompt_types", default=None,
    help=(
        "Comma-separated prompt types to generate. "
        "Valid: solid, dead-code, security, architecture, test-gaps, performance, deps. "
        "Default: all."
    ))
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def prompts(working_dir, output_dir, prompt_types, quiet):
    """
    Generate reusable analysis prompts from codebase scanning (no API key needed).

    \b
    Scans the repo and produces structured prompts you can paste into any LLM
    for targeted code analysis.  No LLM calls — purely deterministic.

    \b
    Prompt types:
      solid         SOLID principle violations
      dead-code     Dead code paths
      security      Security review
      architecture  Architecture review
      test-gaps     Test coverage gaps
      performance   Performance bottlenecks
      deps          Dependency risks

    \b
    Examples:
      repoforge prompts -w .                              # all prompts to stdout
      repoforge prompts -w . --type security,architecture # specific types
      repoforge prompts -w . -o prompts/                  # individual .txt files
    """
    import sys

    from .prompts_cmd import (
        PROMPT_TYPES,
        generate_prompts,
        render_prompts_markdown,
        write_individual_prompts,
    )

    types_list = None
    if prompt_types:
        types_list = [t.strip() for t in prompt_types.split(",") if t.strip()]
        invalid = [t for t in types_list if t not in PROMPT_TYPES]
        if invalid:
            click.echo(
                f"Unknown prompt type(s): {', '.join(invalid)}\n"
                f"Valid types: {', '.join(PROMPT_TYPES)}",
                err=True,
            )
            sys.exit(1)

    if not quiet:
        label = ", ".join(types_list) if types_list else "all"
        click.echo(f"Generating analysis prompts ({label}) for {working_dir} ...", err=True)

    result = generate_prompts(workspace=working_dir, types=types_list)

    if not result:
        click.echo("No prompts generated.", err=True)
        sys.exit(1)

    if output_dir:
        written = write_individual_prompts(result, output_dir)
        if not quiet:
            click.echo(f"Written {len(written)} prompt(s) to {output_dir}/", err=True)
            for w in written:
                click.echo(f"  {w}", err=True)
    else:
        md = render_prompts_markdown(result)
        click.echo(md)


# ---------------------------------------------------------------------------
# validate-skills subcommand
# ---------------------------------------------------------------------------


@main.command(name="validate-skills")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--strict", is_flag=True, default=False,
    help="Also require ## Examples section in each SKILL.md.")
@click.option("--max-lines", default=400, show_default=True, type=int,
    help="Maximum allowed lines per SKILL.md file.")
@click.option("--fmt", "fmt",
    default="text", show_default=True,
    type=click.Choice(["text", "json"], case_sensitive=False),
    help="Output format for the report.")
@click.option("--fail-on",
    default="error", show_default=True,
    type=click.Choice(["error", "warning"], case_sensitive=False),
    help="Exit code 1 when violations at this level (or above) are found.")
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def validate_skills(path, strict, max_lines, fmt, fail_on, quiet):
    """
    Validate SKILL.md files against the standard format (no API key needed).

    \b
    Scans PATH recursively for *.md files that contain YAML frontmatter with
    a 'name:' field, then runs deterministic checks on each file:
      - YAML frontmatter with required keys: name, description, version
      - Required sections: ## Critical Rules
      - File size within --max-lines limit
      - No forbidden syntax (Templater <% blocks, raw HTML tags)
      - (--strict) ## Examples section presence

    \b
    Exit codes:
      0 — all files passed (or no SKILL.md files found)
      1 — one or more violations found at --fail-on level

    \b
    Examples:
      repoforge validate-skills                          # scan current dir
      repoforge validate-skills ~/.claude/skills/        # scan specific dir
      repoforge validate-skills --strict                 # also require Examples
      repoforge validate-skills --max-lines 300          # stricter size limit
      repoforge validate-skills --fmt json               # JSON output for CI
      repoforge validate-skills --fail-on warning        # fail on any issue
    """
    import sys
    from pathlib import Path as _Path

    from .skill_validator import SkillValidator

    target = _Path(path).resolve()

    if not quiet:
        click.echo(f"Scanning {target} for SKILL.md files ...", err=True)

    validator = SkillValidator(
        max_lines=max_lines,
        strict=strict,
        fail_on=fail_on,
    )

    if target.is_file():
        from .skill_validator import FileResult, ValidationResult
        file_result = validator.validate_file(target)
        result = ValidationResult(
            files_scanned=1,
            results=[file_result],
        )
    else:
        result = validator.validate_directory(target)

    report = validator.report(result, fmt=fmt)
    click.echo(report)

    if not quiet and result.files_scanned > 0:
        click.echo(
            f"\nSummary: {result.files_scanned} file(s) scanned, "
            f"{result.total_errors} error(s), "
            f"{result.total_warnings} warning(s)",
            err=True,
        )

    # Exit code
    if fail_on == "warning":
        should_fail = result.total_errors > 0 or result.total_warnings > 0
    else:
        should_fail = result.total_errors > 0

    if should_fail:
        if not quiet:
            click.echo(
                f"\nValidation failed: {result.total_errors} error(s), "
                f"{result.total_warnings} warning(s).",
                err=True,
            )
        sys.exit(1)


# ---------------------------------------------------------------------------
# index subcommand — build semantic search index
# ---------------------------------------------------------------------------

@main.command()
@click.option("-w", "--workspace",
    default=".", show_default=True,
    help="Path to the repo root.",
    type=click.Path(exists=True, file_okay=False),
)
@click.option("-o", "--output-dir", "output_dir",
    default=".repoforge/search_index/", show_default=True,
    help="Directory to save the search index.",
    type=click.Path(),
)
@click.option("--model", "embedding_model",
    default=None,
    help="Embedding model (litellm format). Default: text-embedding-3-small.",
)
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def index(workspace, output_dir, embedding_model, quiet):
    """
    Build a semantic search index from codebase entities (requires API key).

    \b
    Scans the repo, extracts symbols and modules, builds a graph,
    generates embeddings via litellm, and saves a FAISS index to disk.

    \b
    Requires: pip install repoforge-ai[search]

    \b
    Examples:
      repoforge index -w .
      repoforge index -w . -o my_index/
      repoforge index -w . --model text-embedding-3-large
    """
    import sys
    from pathlib import Path

    from .search import SEARCH_AVAILABLE

    if not SEARCH_AVAILABLE:
        click.echo(
            "Error: faiss-cpu is required for semantic search.\n"
            "Install with: pip install repoforge-ai[search]",
            err=True,
        )
        sys.exit(1)

    from .graph import build_graph_v2
    from .search import BM25Index, Embedder, SearchIndex
    from .search.prepare import prepare_all
    from .symbols import build_symbol_graph

    root = str(Path(workspace).resolve())

    # 1. Extract symbols
    if not quiet:
        print("Extracting symbols...", file=sys.stderr)
    sym_graph = build_symbol_graph(root)
    symbols = list(sym_graph.symbols.values())

    # 2. Build file-level graph for nodes
    if not quiet:
        print("Building dependency graph...", file=sys.stderr)
    code_graph = build_graph_v2(root)
    nodes = list(code_graph.nodes)

    # 3. Prepare searchable text entities
    entities = prepare_all(symbols=symbols, nodes=nodes)

    if not entities:
        click.echo("No entities found to index.", err=True)
        sys.exit(1)

    ids = [e[0] for e in entities]
    types = [e[1] for e in entities]
    texts = [e[2] for e in entities]

    n_symbols = sum(1 for t in types if t == "symbol")
    n_nodes = sum(1 for t in types if t == "node")

    if not quiet:
        print(
            f"Indexing {n_symbols} symbols, {n_nodes} nodes...",
            file=sys.stderr,
        )

    out = Path(output_dir)

    # 4a. Build BM25 index (always — no external dependencies)
    bm25_index = BM25Index()
    bm25_index.add(texts=texts, ids=ids, entity_types=types)
    bm25_index.save(out)
    if not quiet:
        print(f"BM25 index saved ({bm25_index.size} documents)", file=sys.stderr)

    # 4b. Build FAISS semantic index
    embedder_kwargs = {}
    if embedding_model:
        embedder_kwargs["model"] = embedding_model
    embedder = Embedder(**embedder_kwargs)
    search_index = SearchIndex(embedder=embedder)
    search_index.add(texts=texts, ids=ids, types=types)

    # 5. Save
    search_index.save(out)

    if not quiet:
        print(
            f"Index saved to {out} ({search_index.size} vectors, dim={search_index.dimension})",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# query subcommand — search the semantic index
# ---------------------------------------------------------------------------

@main.command()
@click.argument("query_text")
@click.option("--top-k", default=10, show_default=True, type=int,
    help="Maximum number of results.")
@click.option("--index-dir",
    default=".repoforge/search_index/", show_default=True,
    help="Directory containing the search index.",
    type=click.Path(),
)
@click.option("--json", "as_json", is_flag=True, default=False,
    help="Output results as JSON.")
@click.option("--model", "embedding_model",
    default=None,
    help="Embedding model (must match the model used to build the index).",
)
@click.option("--search-mode", "search_mode",
    default="hybrid", show_default=True,
    type=click.Choice(["hybrid", "semantic", "bm25"], case_sensitive=False),
    help="Search mode: hybrid (default), semantic, or bm25.",
)
def query(query_text, top_k, index_dir, as_json, embedding_model, search_mode):
    """
    Search the index for matching entities.

    \b
    Loads a pre-built index from disk and returns the most similar
    codebase entities. Supports hybrid (BM25 + semantic), pure semantic,
    or pure BM25 search modes.

    \b
    Examples:
      repoforge query "authentication logic"
      repoforge query "database connection" --top-k 5
      repoforge query "user service" --json
      repoforge query "auth" --search-mode bm25
    """
    import json as json_mod
    import sys
    from pathlib import Path

    from .search import SEARCH_AVAILABLE, BM25Index

    idx_path = Path(index_dir)
    if not idx_path.exists():
        click.echo(
            f"Error: Index not found at {idx_path}\n"
            "Run 'repoforge index' first to build the search index.",
            err=True,
        )
        sys.exit(1)

    results = []

    if search_mode == "bm25":
        bm25_index = BM25Index.load(idx_path)
        results = bm25_index.search(query_text, top_k=top_k)

    elif search_mode == "semantic":
        if not SEARCH_AVAILABLE:
            click.echo(
                "Error: faiss-cpu is required for semantic search.\n"
                "Install with: pip install repoforge-ai[search]",
                err=True,
            )
            sys.exit(1)

        from .search import Embedder, SearchIndex

        embedder_kwargs = {}
        if embedding_model:
            embedder_kwargs["model"] = embedding_model
        embedder = Embedder(**embedder_kwargs)
        search_index = SearchIndex.load(idx_path, embedder=embedder)
        results = search_index.search(query_text, top_k=top_k)

    else:  # hybrid (default)
        embedder = None
        if SEARCH_AVAILABLE:
            from .search import Embedder

            embedder_kwargs = {}
            if embedding_model:
                embedder_kwargs["model"] = embedding_model
            embedder = Embedder(**embedder_kwargs)

        from .search import HybridSearchIndex

        hybrid_index = HybridSearchIndex.load(idx_path, embedder=embedder)
        results = hybrid_index.search(query_text, top_k=top_k)

    if not results:
        click.echo("No results found.", err=True)
        sys.exit(0)

    if as_json:
        output = json_mod.dumps(
            [
                {
                    "score": r.score,
                    "entity_type": r.entity_type,
                    "entity_id": r.entity_id,
                    "text": r.text,
                }
                for r in results
            ],
            indent=2,
            ensure_ascii=False,
        )
        click.echo(output)
    else:
        for r in results:
            snippet = r.text[:80].replace("\n", " ")
            click.echo(f"{r.score:.4f} | {r.entity_type:8s} | {r.entity_id} | {snippet}")


# ---------------------------------------------------------------------------
# blast-radius subcommand (#14 + #15)
# ---------------------------------------------------------------------------

@main.command("blast-radius")
@click.argument("target", required=False)
@click.option("-w", "--working-dir", default=".", show_default=True,
    help="Path to the repo to analyze.",
    type=click.Path(exists=True, file_okay=False))
@click.option("--files", multiple=True,
    help="File paths to analyze (alternative to commit target).")
@click.option("--depth", default=3, show_default=True, type=int,
    help="Max BFS depth for transitive dependencies.")
@click.option("--max-files", default=50, show_default=True, type=int,
    help="Cap on total files in result.")
@click.option("--include-tests/--no-include-tests", default=True, show_default=True,
    help="Include test files in results.")
@click.option("--ast", is_flag=True, default=False,
    help="Enrich with tree-sitter AST symbols (requires intelligence extra).")
@click.option("--json", "as_json", is_flag=True, default=False,
    help="Output as JSON.")
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def blast_radius_cmd(target, working_dir, files, depth, max_files, include_tests, ast, as_json, quiet):
    """Compute blast radius of a change (no API key needed).

    \b
    Analyze which files are transitively affected by a change.
    Accepts a git commit/ref OR a list of files.

    \b
    Examples:
      repoforge blast-radius HEAD                    # from latest commit
      repoforge blast-radius abc123                   # from specific commit
      repoforge blast-radius --files src/auth.py --files src/models.py
      repoforge blast-radius HEAD --ast               # with tree-sitter symbols
      repoforge blast-radius --files cli.py --json    # JSON output
    """
    import json as json_mod
    import sys

    from .blast_radius import (
        blast_radius_from_commit,
        blast_radius_from_files,
        format_blast_radius,
    )

    if not target and not files:
        # Default: working tree changes
        from .blast_radius import _get_changed_files_working_tree
        wt_files = _get_changed_files_working_tree(working_dir)
        if not wt_files:
            click.echo("No changed files found in working tree. "
                       "Specify a commit or --files.", err=True)
            sys.exit(1)
        files = tuple(wt_files)

    if not quiet:
        if target:
            print(f"Computing blast radius for commit {target} in {working_dir} ...",
                  file=sys.stderr)
        else:
            print(f"Computing blast radius for {len(files)} file(s) in {working_dir} ...",
                  file=sys.stderr)

    if target:
        report = blast_radius_from_commit(
            working_dir, target,
            max_depth=depth, max_files=max_files,
            include_tests=include_tests, with_ast=ast,
        )
    else:
        report = blast_radius_from_files(
            working_dir, list(files),
            max_depth=depth, max_files=max_files,
            include_tests=include_tests, with_ast=ast,
        )

    if as_json:
        data = {
            "changed_files": report.changed_files,
            "affected_files": report.affected_files,
            "affected_tests": report.affected_tests,
            "risk_level": report.risk_level,
            "depth": report.depth,
            "exceeded_cap": report.exceeded_cap,
            "total_affected": report.total_affected,
        }
        if report.symbols:
            data["symbols"] = [
                {"name": s.name, "kind": s.kind, "file": s.file,
                 "line": s.line, "signature": s.signature}
                for s in report.symbols
            ]
        click.echo(json_mod.dumps(data, indent=2))
    else:
        click.echo(format_blast_radius(report))


# ---------------------------------------------------------------------------
# change-impact subcommand (#16)
# ---------------------------------------------------------------------------

@main.command("change-impact")
@click.argument("target", required=False)
@click.option("-w", "--working-dir", default=".", show_default=True,
    help="Path to the repo to analyze.",
    type=click.Path(exists=True, file_okay=False))
@click.option("--files", multiple=True,
    help="File paths to analyze (alternative to commit target).")
@click.option("--json", "as_json", is_flag=True, default=False,
    help="Output as JSON.")
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def change_impact_cmd(target, working_dir, files, as_json, quiet):
    """Identify which tests need to run for a change (no API key needed).

    \b
    Given changed files (from a commit or file list), maps each changed
    file to the test files that exercise it.

    \b
    Examples:
      repoforge change-impact HEAD
      repoforge change-impact abc123
      repoforge change-impact --files src/auth.py --files src/models.py
    """
    import json as json_mod
    import sys

    from .change_impact import analyze_change_impact, format_change_impact

    if not target and not files:
        click.echo("Specify a commit SHA or --files.", err=True)
        sys.exit(1)

    if not quiet:
        print(f"Analyzing change impact in {working_dir} ...", file=sys.stderr)

    report = analyze_change_impact(
        working_dir,
        files=list(files) if files else None,
        commit=target,
    )

    if as_json:
        data = {
            "changed_files": report.changed_files,
            "tests_to_run": report.all_tests,
            "untested_files": report.untested_files,
            "mappings": [
                {
                    "source": m.source_file,
                    "graph_tests": m.graph_tests,
                    "convention_tests": m.convention_tests,
                    "all_tests": m.all_tests,
                }
                for m in report.mappings
            ],
        }
        click.echo(json_mod.dumps(data, indent=2))
    else:
        click.echo(format_change_impact(report))


# ---------------------------------------------------------------------------
# co-change subcommand (#17)
# ---------------------------------------------------------------------------

@main.command("co-change")
@click.option("-w", "--working-dir", default=".", show_default=True,
    help="Path to the repo to analyze.",
    type=click.Path(exists=True, file_okay=False))
@click.option("--threshold", default=0.5, show_default=True, type=float,
    help="Minimum Jaccard similarity to include (0.0-1.0).")
@click.option("--min-commits", default=3, show_default=True, type=int,
    help="Minimum co-change count to include.")
@click.option("--max-commits", default=500, show_default=True, type=int,
    help="Maximum commits to analyze.")
@click.option("--since", default=None,
    help="Git date filter (e.g., '6 months ago').")
@click.option("--no-imports", is_flag=True, default=False,
    help="Skip cross-referencing with dependency graph.")
@click.option("--json", "as_json", is_flag=True, default=False,
    help="Output as JSON.")
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def co_change_cmd(working_dir, threshold, min_commits, max_commits, since, no_imports, as_json, quiet):
    """Detect files that always change together (no API key needed).

    \b
    Mines git history to find co-change pairs — files that frequently
    appear in the same commits. Flags hidden coupling when pairs have
    no import relationship.

    \b
    Examples:
      repoforge co-change -w .
      repoforge co-change -w . --threshold 0.7
      repoforge co-change -w . --since "6 months ago"
      repoforge co-change -w . --no-imports --json
    """
    import json as json_mod
    import sys

    from .co_change import detect_co_changes, format_co_changes

    if not quiet:
        print(f"Mining co-change patterns in {working_dir} ...", file=sys.stderr)

    report = detect_co_changes(
        working_dir,
        threshold=threshold,
        min_commits=min_commits,
        max_commits=max_commits,
        since=since,
        check_imports=not no_imports,
    )

    if as_json:
        data = {
            "commits_analyzed": report.commits_analyzed,
            "files_analyzed": report.files_analyzed,
            "threshold": report.threshold,
            "pairs": [
                {
                    "file_a": p.file_a,
                    "file_b": p.file_b,
                    "co_change_count": p.co_change_count,
                    "jaccard": p.jaccard,
                    "has_import_link": p.has_import_link,
                    "confidence": p.confidence,
                }
                for p in report.pairs
            ],
        }
        click.echo(json_mod.dumps(data, indent=2))
    else:
        click.echo(format_co_changes(report))


# ---------------------------------------------------------------------------
# ownership subcommand (#18)
# ---------------------------------------------------------------------------

@main.command("ownership")
@click.option("-w", "--working-dir", default=".", show_default=True,
    help="Path to the repo to analyze.",
    type=click.Path(exists=True, file_okay=False))
@click.option("--bus-factor", is_flag=True, default=False,
    help="Show bus-factor risk analysis.")
@click.option("--max-commits", default=1000, show_default=True, type=int,
    help="Maximum commits to analyze.")
@click.option("--since", default=None,
    help="Git date filter (e.g., '1 year ago').")
@click.option("--json", "as_json", is_flag=True, default=False,
    help="Output as JSON.")
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def ownership_cmd(working_dir, bus_factor, max_commits, since, as_json, quiet):
    """Compute file/module ownership and bus factor (no API key needed).

    \b
    Analyzes git history to compute per-file and per-directory ownership
    concentration. Flags bus-factor risks where knowledge is concentrated
    in a single contributor.

    \b
    Examples:
      repoforge ownership -w .
      repoforge ownership -w . --bus-factor
      repoforge ownership -w . --since "1 year ago"
      repoforge ownership -w . --bus-factor --json
    """
    import json as json_mod
    import sys

    from .ownership import analyze_ownership, format_ownership

    if not quiet:
        print(f"Analyzing ownership in {working_dir} ...", file=sys.stderr)

    report = analyze_ownership(
        working_dir,
        max_commits=max_commits,
        since=since,
        bus_factor_only=False,
    )

    if as_json:
        data = {
            "total_contributors": report.total_contributors,
            "total_files": report.total_files,
            "directories": [
                {
                    "directory": d.directory,
                    "file_count": d.file_count,
                    "total_commits": d.total_commits,
                    "top_contributor": d.top_contributor,
                    "ownership_ratio": round(d.ownership_ratio, 3),
                    "bus_factor": d.bus_factor,
                    "risk_level": d.risk_level,
                }
                for d in report.directories
            ],
        }
        if bus_factor:
            data["bus_factor_risks"] = [
                {
                    "file": f.file,
                    "top_contributor": f.top_contributor,
                    "ownership_ratio": round(f.ownership_ratio, 3),
                    "bus_factor": f.bus_factor,
                    "risk_level": f.risk_level,
                    "total_commits": f.total_commits,
                }
                for f in report.bus_factor_risks
            ]
        click.echo(json_mod.dumps(data, indent=2))
    else:
        click.echo(format_ownership(report, bus_factor=bus_factor))


# ---------------------------------------------------------------------------
# Backwards compatibility: allow `repoforge` (no subcommand) to run skills
# ---------------------------------------------------------------------------

@main.command(hidden=True, name="run")
@_common_options
@click.option("-o", "--output-dir", default=".claude", show_default=True)
@click.option("--no-opencode", is_flag=True, default=False)
def run_default(working_dir, model, api_key, api_base, dry_run, quiet, max_files_per_layer, output_dir, no_opencode):
    """Alias for 'skills' (backwards compatibility)."""
    from .generator import generate_artifacts
    generate_artifacts(
        working_dir=working_dir, output_dir=output_dir,
        model=model, api_key=api_key, api_base=api_base,
        also_opencode=not no_opencode, verbose=not quiet, dry_run=dry_run,
    )


if __name__ == "__main__":
    main()
