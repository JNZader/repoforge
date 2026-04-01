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
      skills-from-docs Generate SKILL.md from documentation (URL, GitHub repo, local dir)
      score            Score quality of generated SKILL.md files (no API key needed)
      scan             Security scan generated output for issues (no API key needed)
      docs             Generate technical documentation (Docsify-ready, GH Pages compatible)
      export           Flatten repo into a single LLM-optimized file (no API key needed)
      compress         Token-optimize generated .md files (no API key needed)
      graph            Build a code knowledge graph from scanner data (no API key needed)

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
def docs(working_dir, model, api_key, api_base, dry_run, quiet,
         max_files_per_layer,
         output_dir, language, project_name, complexity, theme, do_serve, port, serve_only,
         chunked, do_verify, verify_model, no_verify_docs, facts_only, incremental):
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
    """
    from .docs_generator import generate_docs
    from .server import serve_docs

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
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def graph(workspace, output_path, fmt, blast_radius, v2, depth, max_files, include_tests, quiet):
    """
    Build a code knowledge graph from scanner data (no API key needed).

    \b
    Scans the repo and builds a lightweight dependency graph based on
    import/export name matching. No tree-sitter needed — uses RepoMap data.

    \b
    Output formats:
      summary  — Human-readable stats (modules, deps, most connected)
      mermaid  — Mermaid flowchart diagram (for docs / README)
      json     — D3/Cytoscape-compatible nodes + edges
      dot      — Graphviz DOT format

    \b
    Examples:
      repoforge graph -w .                             # summary to stdout
      repoforge graph -w . --format mermaid            # Mermaid diagram
      repoforge graph -w . --format json -o graph.json # JSON to file
      repoforge graph -w . --format dot -o graph.dot   # DOT to file
      repoforge graph -w . --blast-radius src/auth.py  # blast radius
    """
    import sys

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
        # Normal format output
        if fmt == "mermaid":
            output = code_graph.to_mermaid()
        elif fmt == "json":
            output = code_graph.to_json()
        elif fmt == "dot":
            output = code_graph.to_dot()
        else:
            output = code_graph.summary()

    # Write output
    if output_path:
        from pathlib import Path
        Path(output_path).write_text(output, encoding="utf-8")
        if not quiet:
            print(f"Written to {output_path}", file=sys.stderr)
    else:
        click.echo(output)


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
    type=click.Choice(["dependency", "directory", "callflow", "all"], case_sensitive=False),
    help="Diagram type to generate.")
@click.option("--max-nodes", default=40, show_default=True, type=int,
    help="Max nodes in dependency diagram.")
@click.option("--max-depth", default=3, show_default=True, type=int,
    help="Max depth for directory/call flow diagrams.")
@click.option("--entry", default=None,
    help="Entry point file for call flow diagram (auto-detected if not set).")
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def diagram(workspace, output_path, diagram_type, max_nodes, max_depth, entry, quiet):
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
      all         — All diagram types combined

    \b
    Examples:
      repoforge diagram -w .                          # all diagrams to stdout
      repoforge diagram -w . --type dependency        # dependency graph only
      repoforge diagram -w . --type callflow --entry src/main.py
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
    Generate SKILL.md from documentation (URL, GitHub repo, or local dir).

    \b
    Accepts three types of sources:
      - HTTP/HTTPS URL: scrapes documentation page
      - GitHub repo URL: clones and scans .md files
      - Local directory: reads .md/.html files recursively

    \b
    No API key needed — extraction and generation are deterministic.

    \b
    Examples:
      repoforge skills-from-docs -w https://docs.example.com/guide
      repoforge skills-from-docs -w https://github.com/org/repo -o .claude/skills
      repoforge skills-from-docs -w /path/to/docs --name my-lib
      repoforge skills-from-docs -w /path/to/docs --dry-run
      repoforge skills-from-docs -w /path/to/docs --score
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
