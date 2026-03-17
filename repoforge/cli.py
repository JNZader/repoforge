"""
cli.py - Command-line interface for RepoForge.

Three modes:

  repoforge skills [options]   — Generate SKILL.md + AGENT.md for Claude Code / OpenCode
  repoforge docs   [options]   — Generate technical documentation (Docsify / GH Pages ready)
  repoforge export [options]   — Flatten repo into a single LLM-optimized file (no API key needed)

Quick usage:
  repoforge skills -w /my/repo --model claude-haiku-3-5
  repoforge docs   -w /my/repo --lang Spanish -o docs
  repoforge docs   -w /my/repo --model gpt-4o-mini --lang English --dry-run
  repoforge export -w /my/repo -o context.md
  repoforge export -w /my/repo --max-tokens 100000 --format xml
  repoforge skills --model ollama/qwen2.5-coder:14b   # free local
  repoforge skills --model github/gpt-4o-mini          # GitHub Copilot
"""

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
    return f


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="repoforge")
def main():
    """
    RepoForge — AI-powered code analysis tool.

    \b
    Commands:
      skills   Generate SKILL.md + AGENT.md for Claude Code / OpenCode
      docs     Generate technical documentation (Docsify-ready, GH Pages compatible)
      export   Flatten repo into a single LLM-optimized file (no API key needed)

    \b
    Examples:
      repoforge skills -w .
      repoforge docs -w . --lang Spanish -o docs
      repoforge docs --model gpt-4o-mini --dry-run
      repoforge export -w . -o context.md
      repoforge export -w . --max-tokens 100000 --format xml
    """
    pass


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
def skills(working_dir, model, api_key, api_base, dry_run, quiet,
           output_dir, no_opencode, complexity, do_serve, port, serve_only):
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
        )

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
def docs(working_dir, model, api_key, api_base, dry_run, quiet,
         output_dir, language, project_name, complexity, theme, do_serve, port, serve_only):
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
@click.option("-q", "--quiet", is_flag=True, default=False,
    help="Suppress progress output.")
def export(working_dir, output_path, max_tokens, no_contents, fmt, quiet):
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
    )

    if output_path:
        if not quiet:
            tokens = len(result) // 4
            print(f"Written to {output_path} (~{tokens:,} tokens)", file=sys.stderr)
    else:
        click.echo(result)


# ---------------------------------------------------------------------------
# Backwards compatibility: allow `repoforge` (no subcommand) to run skills
# ---------------------------------------------------------------------------

@main.command(hidden=True, name="run")
@_common_options
@click.option("-o", "--output-dir", default=".claude", show_default=True)
@click.option("--no-opencode", is_flag=True, default=False)
def run_default(working_dir, model, api_key, api_base, dry_run, quiet, output_dir, no_opencode):
    """Alias for 'skills' (backwards compatibility)."""
    from .generator import generate_artifacts
    generate_artifacts(
        working_dir=working_dir, output_dir=output_dir,
        model=model, api_key=api_key, api_base=api_base,
        also_opencode=not no_opencode, verbose=not quiet, dry_run=dry_run,
    )


if __name__ == "__main__":
    main()
