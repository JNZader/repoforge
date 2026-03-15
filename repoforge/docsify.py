"""
docsify.py - Generate Docsify-ready static files for GitHub Pages.

Generates:
  index.html   - Docsify app shell (zero dependencies to install)
  _sidebar.md  - Navigation sidebar
  .nojekyll    - Tells GH Pages not to run Jekyll (needed for _ files)

The generated docs/ folder can be served by:
  - GitHub Pages (Settings → Pages → Source: /docs on main)
  - Any static server: npx serve docs / python3 -m http.server
  - Locally by opening index.html directly (with ?filename query won't work, use a server)
"""

from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_docsify_files(
    output_dir: Path,
    project_name: str,
    chapters: list[dict],
    language: str = "English",
    theme: str = "vue",
) -> list[str]:
    """
    Generate Docsify infrastructure files in output_dir.

    Args:
        output_dir:   Path to the docs directory (already created)
        project_name: Used in page title and header
        chapters:     List of {"file": str, "title": str, "description": str}
                      Only include chapters that were actually generated
        language:     Documentation language (for HTML lang attribute)
        theme:        Docsify CSS theme: "vue" (default), "dark", "buble", "pure"

    Returns list of generated file paths.
    """
    output_dir = Path(output_dir)
    generated = []

    # 1. _sidebar.md
    sidebar_path = output_dir / "_sidebar.md"
    sidebar_path.write_text(_build_sidebar(project_name, chapters), encoding="utf-8")
    generated.append(str(sidebar_path))

    # 2. .nojekyll
    nojekyll_path = output_dir / ".nojekyll"
    nojekyll_path.write_text("", encoding="utf-8")
    generated.append(str(nojekyll_path))

    # 3. index.html
    index_path = output_dir / "index.html"
    lang_code = _language_to_code(language)
    index_path.write_text(
        _build_index_html(project_name, lang_code, theme),
        encoding="utf-8"
    )
    generated.append(str(index_path))

    return generated


# ---------------------------------------------------------------------------
# _sidebar.md
# ---------------------------------------------------------------------------

def _build_sidebar(project_name: str, chapters: list[dict]) -> str:
    """
    Build _sidebar.md for both flat (single project) and hierarchical (monorepo) layouts.

    Monorepo chapters have "subdir" set (e.g. "frontend", "backend").
    Root-level chapters have subdir=None.

    Flat example:
        - **MyProject**
          - [Home](index)
          - [Overview](01-overview)

    Monorepo example:
        - **MyProject**
          - [Home](index)
          - [Architecture](03-architecture)
          - **Frontend (Frontend App)**
            - [Frontend Layer](frontend/index)
            - [Components](frontend/05-components)
          - **Backend (Web Service)**
            - [Backend Layer](backend/index)
            - [API Reference](backend/06-api-reference)
    """
    has_subdirs = any(c.get("subdir") for c in chapters)

    if not has_subdirs:
        # Flat layout — single project
        lines = [f"- **{project_name}**\n"]
        for chapter in chapters:
            slug = chapter["file"].replace(".md", "")
            lines.append(f"  - [{chapter['title']}]({slug})")
        return "\n".join(lines) + "\n"

    # Hierarchical layout — monorepo
    lines = [f"- **{project_name}**\n"]

    # Root-level chapters first
    for ch in chapters:
        if not ch.get("subdir"):
            slug = ch["file"].replace(".md", "")
            lines.append(f"  - [{ch['title']}]({slug})")

    # Per-layer chapters grouped by subdir
    seen_subdirs: list[str] = []
    for ch in chapters:
        subdir = ch.get("subdir")
        if not subdir:
            continue
        if subdir not in seen_subdirs:
            seen_subdirs.append(subdir)
            ptype = ch.get("project_type", "").replace("_", " ").title()
            label = f"{subdir.title()} ({ptype})" if ptype else subdir.title()
            lines.append(f"\n  - **{label}**")
        slug = f"{subdir}/{ch['file'].replace('.md', '')}"
        lines.append(f"    - [{ch['title']}]({slug})")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# index.html
# ---------------------------------------------------------------------------

def _build_index_html(project_name: str, lang_code: str, theme: str) -> str:
    theme_url = _theme_url(theme)
    # Escape for HTML/JS
    safe_name = project_name.replace("'", "\\'").replace('"', "&quot;")

    return f"""<!DOCTYPE html>
<html lang="{lang_code}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>{project_name}</title>
  <meta name="description" content="Documentation for {project_name} — generated by RepoForge">

  <!-- Docsify theme -->
  <link rel="stylesheet" href="{theme_url}">

  <!-- Code highlighting -->
  <link rel="stylesheet" href="//cdn.jsdelivr.net/npm/prismjs@1/themes/prism-tomorrow.min.css">

  <style>
    /* Mermaid diagram centering */
    .mermaid {{ text-align: center; margin: 1.5em 0; }}
    /* Sidebar project name */
    .sidebar > h1 {{ font-size: 1.1rem; font-weight: 700; }}
  </style>
</head>
<body>
  <div id="app">Loading...</div>

  <script>
    window.$docsify = {{
      name: '{safe_name}',
      repo: '',

      // Sidebar
      loadSidebar: '_sidebar.md',
      subMaxLevel: 3,
      auto2top: true,

      // Search plugin
      search: {{
        maxAge: 86400000,
        paths: 'auto',
        placeholder: 'Search...',
        noData: 'No results',
        depth: 3,
        hideOtherSidebarContent: false,
      }},

      // Tab size for code blocks
      tabSize: 2,

      // Scroll to top on page change
      scrollToTop: true,
    }};
  </script>

  <!-- Docsify core -->
  <script src="//cdn.jsdelivr.net/npm/docsify@4/lib/docsify.min.js"></script>

  <!-- Search plugin -->
  <script src="//cdn.jsdelivr.net/npm/docsify@4/lib/plugins/search.min.js"></script>

  <!-- Code highlighting (Prism) -->
  <script src="//cdn.jsdelivr.net/npm/prismjs@1/components/prism-core.min.js"></script>
  <script src="//cdn.jsdelivr.net/npm/prismjs@1/plugins/autoloader/prism-autoloader.min.js"></script>

  <!-- Mermaid diagrams -->
  <script src="//cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <script>
    // Docsify + Mermaid integration
    window.$docsify.plugins = [
      function(hook) {{
        hook.doneEach(function() {{
          // Find all ```mermaid blocks rendered as <code class="lang-mermaid">
          document.querySelectorAll('pre code.lang-mermaid, pre code.language-mermaid').forEach(function(el) {{
            var pre = el.parentElement;
            var div = document.createElement('div');
            div.className = 'mermaid';
            div.textContent = el.textContent;
            pre.replaceWith(div);
          }});
          if (typeof mermaid !== 'undefined') {{
            mermaid.init(undefined, '.mermaid');
          }}
        }});
      }}
    ];
  </script>

  <!-- Copy to clipboard for code blocks -->
  <script src="//cdn.jsdelivr.net/npm/docsify-copy-code@2/dist/docsify-copy-code.min.js"></script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _theme_url(theme: str) -> str:
    themes = {
        "vue":   "//cdn.jsdelivr.net/npm/docsify@4/lib/themes/vue.css",
        "dark":  "//cdn.jsdelivr.net/npm/docsify@4/lib/themes/dark.css",
        "buble": "//cdn.jsdelivr.net/npm/docsify@4/lib/themes/buble.css",
        "pure":  "//cdn.jsdelivr.net/npm/docsify@4/lib/themes/pure.css",
    }
    return themes.get(theme, themes["vue"])


def _language_to_code(language: str) -> str:
    """Map documentation language name to HTML lang attribute code."""
    mapping = {
        "english":    "en",
        "spanish":    "es",
        "chinese":    "zh",
        "japanese":   "ja",
        "korean":     "ko",
        "french":     "fr",
        "german":     "de",
        "portuguese": "pt",
        "russian":    "ru",
        "italian":    "it",
        "dutch":      "nl",
    }
    return mapping.get(language.lower(), "en")
