"""Chapter prompts quote tree-sitter signatures, including route decorators."""

import pytest

pytest.importorskip("tree_sitter")
pytest.importorskip("tree_sitter_language_pack")

from repoforge.docs_prompts import get_chapter_prompts
from repoforge.graph_context import format_api_surface
from repoforge.intelligence.extractor_registry import get_ast_registry


PY_ROUTE = """from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/health")
def health(request: Request) -> dict:
    return {"ok": True}
"""

TS_FUNCTION = """export function formatUser(id: string): string {
  return id;
}
"""

PY_SIGNATURE = "def health(request: Request) -> dict"
TS_SIGNATURE = "function formatUser(id: string): string"
ROUTE = '@app.get("/health")'


def test_chapter_prompt_quotes_python_route_and_typescript_function(tmp_path):
    registry = get_ast_registry()
    if registry is None:
        pytest.skip("intelligence extra is not installed")

    app = tmp_path / "app"
    src = tmp_path / "src"
    app.mkdir()
    src.mkdir()
    (app / "main.py").write_text(PY_ROUTE)
    (src / "user.ts").write_text(TS_FUNCTION)

    surface = format_api_surface(
        str(tmp_path),
        ["app/main.py", "src/user.ts"],
    )
    assert ROUTE in surface
    assert PY_SIGNATURE in surface
    assert TS_SIGNATURE in surface
    assert "from AST analysis" in surface

    repo_map = {
        "root": str(tmp_path),
        "tech_stack": ["Python", "TypeScript"],
        "entry_points": ["app/main.py"],
        "config_files": [],
        "layers": {
            "main": {
                "path": ".",
                "modules": [
                    {
                        "path": "app/main.py",
                        "name": "main",
                        "language": "Python",
                        "exports": ["health"],
                        "imports": ["fastapi"],
                        "summary_hint": "health route",
                    },
                    {
                        "path": "src/user.ts",
                        "name": "user",
                        "language": "TypeScript",
                        "exports": ["formatUser"],
                        "imports": [],
                        "summary_hint": "format a user id",
                    },
                ],
            }
        },
        "stats": {
            "total_files": 2,
            "by_extension": {".py": 1, ".ts": 1},
            "rg_available": False,
            "rg_version": None,
        },
    }
    chapters = get_chapter_prompts(
        repo_map,
        "English",
        "Fixture",
        short_graph_context=surface,
    )
    quoted = "\n".join(chapter["user"] for chapter in chapters)
    assert ROUTE in quoted
    assert PY_SIGNATURE in quoted
    assert TS_SIGNATURE in quoted
