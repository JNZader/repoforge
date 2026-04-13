"""
tests/test_deep_analysis.py — Tests for 5-layer analysis module.

Tests cover:
- Layer 1: AST extraction for Python, TS/JS, Go
- Layer 2: Call graph extraction
- Layer 3: CFG extraction (branches, loops, try/except)
- Layer 4: DFG extraction (def-use chains)
- Layer 5: PDG construction (combined CFG+DFG)
- analyze_file() end-to-end
- analyze_repo() end-to-end
- Formatters (text and JSON)
- Cyclomatic complexity calculation
"""

import json
from pathlib import Path

import pytest

from repoforge.deep_analysis import (
    FileAnalysis,
    RepoAnalysis,
    _build_pdg_layer,
    _detect_language,
    _extract_ast_layer,
    _extract_call_edges,
    _extract_cfg_layer,
    _extract_dfg_layer,
    analysis_to_json,
    analyze_file,
    analyze_repo,
    format_analysis,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def python_project(tmp_path):
    """Create a temporary Python project with meaningful code."""
    (tmp_path / "auth.py").write_text("""\
def authenticate(token, secret):
    if not token:
        raise ValueError("Missing token")
    decoded = decode_jwt(token, secret)
    if decoded is None:
        return None
    user = lookup_user(decoded["sub"])
    return user


def decode_jwt(token, secret):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parse_payload(parts[1])
        return payload
    except Exception:
        return None


class AuthService:
    def __init__(self, secret):
        self.secret = secret
""")

    (tmp_path / "utils.py").write_text("""\
def process_items(items, threshold=0.5):
    results = []
    for item in items:
        if item.score > threshold:
            transformed = transform(item)
            results.append(transformed)
        else:
            skipped = item.name
            log_skip(skipped)
    return results


def transform(item):
    name = item.name.upper()
    score = item.score * 100
    return {"name": name, "score": score}
""")

    return tmp_path


@pytest.fixture
def ts_project(tmp_path):
    """Create a temporary TypeScript project."""
    src = tmp_path / "src"
    src.mkdir()

    (src / "handler.ts").write_text("""\
export function handleRequest(req: Request, res: Response) {
    if (!req.headers.authorization) {
        return res.status(401).send("Unauthorized");
    }
    const token = extractToken(req.headers.authorization);
    try {
        const user = validateToken(token);
        return res.json({ user });
    } catch (err) {
        return res.status(403).send("Forbidden");
    }
}

export const processData = (items: Item[]) => {
    for (const item of items) {
        if (item.valid) {
            save(item);
        }
    }
}
""")
    return tmp_path


# ---------------------------------------------------------------------------
# Layer 1: AST
# ---------------------------------------------------------------------------

class TestASTExtraction:
    def test_python_functions(self, python_project):
        content = (python_project / "auth.py").read_text()
        nodes = _extract_ast_layer(content, "auth.py", "python")
        names = [n.name for n in nodes]
        assert "authenticate" in names
        assert "decode_jwt" in names

    def test_python_class(self, python_project):
        content = (python_project / "auth.py").read_text()
        nodes = _extract_ast_layer(content, "auth.py", "python")
        classes = [n for n in nodes if n.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "AuthService"

    def test_python_params(self, python_project):
        content = (python_project / "auth.py").read_text()
        nodes = _extract_ast_layer(content, "auth.py", "python")
        auth_fn = [n for n in nodes if n.name == "authenticate"][0]
        assert "token" in auth_fn.params
        assert "secret" in auth_fn.params

    def test_typescript_functions(self, ts_project):
        content = (ts_project / "src" / "handler.ts").read_text()
        nodes = _extract_ast_layer(content, "src/handler.ts", "typescript")
        names = [n.name for n in nodes]
        assert "handleRequest" in names
        assert "processData" in names

    def test_language_detection(self):
        assert _detect_language("foo.py") == "python"
        assert _detect_language("bar.ts") == "typescript"
        assert _detect_language("baz.go") == "go"
        assert _detect_language("qux.java") == "java"
        assert _detect_language("test.rs") == "rust"
        assert _detect_language("readme.md") == ""

    def test_unsupported_language_returns_empty(self):
        nodes = _extract_ast_layer("some content", "file.txt", "")
        assert nodes == []


# ---------------------------------------------------------------------------
# Layer 2: Call Graph
# ---------------------------------------------------------------------------

class TestCallGraph:
    def test_extracts_calls(self, python_project):
        content = (python_project / "auth.py").read_text()
        ast_nodes = _extract_ast_layer(content, "auth.py", "python")
        edges = _extract_call_edges(content, "auth.py", ast_nodes)
        callers = {e.caller for e in edges}
        callees = {e.callee for e in edges}
        assert "authenticate" in callers
        assert "decode_jwt" in callees
        assert "lookup_user" in callees

    def test_skips_builtins(self, python_project):
        content = (python_project / "auth.py").read_text()
        ast_nodes = _extract_ast_layer(content, "auth.py", "python")
        edges = _extract_call_edges(content, "auth.py", ast_nodes)
        callees = {e.callee for e in edges}
        # 'len' and 'print' should be skipped
        assert "len" not in callees
        assert "ValueError" not in callees  # skipped as well


# ---------------------------------------------------------------------------
# Layer 3: CFG
# ---------------------------------------------------------------------------

class TestCFG:
    def test_python_branches(self, python_project):
        content = (python_project / "auth.py").read_text()
        ast_nodes = _extract_ast_layer(content, "auth.py", "python")
        cfg = _extract_cfg_layer(content, "auth.py", "python", ast_nodes)
        branches = [n for n in cfg if n.node_type == "branch"]
        assert len(branches) >= 2  # authenticate has 2 ifs

    def test_python_loops(self, python_project):
        content = (python_project / "utils.py").read_text()
        ast_nodes = _extract_ast_layer(content, "utils.py", "python")
        cfg = _extract_cfg_layer(content, "utils.py", "python", ast_nodes)
        loops = [n for n in cfg if n.node_type == "loop"]
        assert len(loops) >= 1

    def test_python_try_except(self, python_project):
        content = (python_project / "auth.py").read_text()
        ast_nodes = _extract_ast_layer(content, "auth.py", "python")
        cfg = _extract_cfg_layer(content, "auth.py", "python", ast_nodes)
        try_nodes = [n for n in cfg if n.node_type == "try"]
        assert len(try_nodes) >= 1

    def test_cfg_has_parent_function(self, python_project):
        content = (python_project / "utils.py").read_text()
        ast_nodes = _extract_ast_layer(content, "utils.py", "python")
        cfg = _extract_cfg_layer(content, "utils.py", "python", ast_nodes)
        for node in cfg:
            assert node.parent_function != ""

    def test_typescript_branches(self, ts_project):
        content = (ts_project / "src" / "handler.ts").read_text()
        ast_nodes = _extract_ast_layer(content, "src/handler.ts", "typescript")
        cfg = _extract_cfg_layer(content, "src/handler.ts", "typescript", ast_nodes)
        branches = [n for n in cfg if n.node_type == "branch"]
        assert len(branches) >= 1


# ---------------------------------------------------------------------------
# Layer 4: DFG
# ---------------------------------------------------------------------------

class TestDFG:
    def test_python_def_use_chains(self, python_project):
        content = (python_project / "utils.py").read_text()
        ast_nodes = _extract_ast_layer(content, "utils.py", "python")
        dfg = _extract_dfg_layer(content, "utils.py", "python", ast_nodes)
        variables = {e.variable for e in dfg}
        # 'results' is defined and used in process_items
        assert "results" in variables or "item" in variables

    def test_params_as_definitions(self, python_project):
        content = (python_project / "auth.py").read_text()
        ast_nodes = _extract_ast_layer(content, "auth.py", "python")
        dfg = _extract_dfg_layer(content, "auth.py", "python", ast_nodes)
        # 'token' is a param and should appear as a variable in DFG
        variables = {e.variable for e in dfg}
        assert "token" in variables

    def test_dfg_has_parent_function(self, python_project):
        content = (python_project / "utils.py").read_text()
        ast_nodes = _extract_ast_layer(content, "utils.py", "python")
        dfg = _extract_dfg_layer(content, "utils.py", "python", ast_nodes)
        for edge in dfg:
            assert edge.parent_function != ""


# ---------------------------------------------------------------------------
# Layer 5: PDG
# ---------------------------------------------------------------------------

class TestPDG:
    def test_pdg_combines_cfg_and_dfg(self, python_project):
        content = (python_project / "utils.py").read_text()
        ast_nodes = _extract_ast_layer(content, "utils.py", "python")
        cfg = _extract_cfg_layer(content, "utils.py", "python", ast_nodes)
        dfg = _extract_dfg_layer(content, "utils.py", "python", ast_nodes)
        pdg = _build_pdg_layer(cfg, dfg, "utils.py")
        assert len(pdg) > 0

    def test_pdg_dep_types(self, python_project):
        content = (python_project / "utils.py").read_text()
        ast_nodes = _extract_ast_layer(content, "utils.py", "python")
        cfg = _extract_cfg_layer(content, "utils.py", "python", ast_nodes)
        dfg = _extract_dfg_layer(content, "utils.py", "python", ast_nodes)
        pdg = _build_pdg_layer(cfg, dfg, "utils.py")
        dep_types = {e.dep_type for e in pdg}
        # Should have at least data or control dependencies
        assert dep_types.intersection({"data", "control", "both"})

    def test_pdg_empty_on_no_input(self):
        pdg = _build_pdg_layer([], [], "empty.py")
        assert pdg == []


# ---------------------------------------------------------------------------
# End-to-end: analyze_file
# ---------------------------------------------------------------------------

class TestAnalyzeFile:
    def test_full_depth(self, python_project):
        result = analyze_file(str(python_project), "auth.py", depth=5)
        assert isinstance(result, FileAnalysis)
        assert result.language == "python"
        assert result.depth == 5
        assert len(result.ast_nodes) >= 2
        assert len(result.call_edges) >= 1
        assert len(result.cfg_nodes) >= 1

    def test_partial_depth(self, python_project):
        result = analyze_file(str(python_project), "auth.py", depth=2)
        assert result.depth == 2
        assert len(result.ast_nodes) >= 2
        assert len(result.call_edges) >= 1
        # CFG/DFG/PDG should be empty at depth 2
        assert len(result.cfg_nodes) == 0
        assert len(result.dfg_edges) == 0
        assert len(result.pdg_edges) == 0

    def test_unsupported_file(self, tmp_path):
        (tmp_path / "readme.md").write_text("# Hello")
        result = analyze_file(str(tmp_path), "readme.md", depth=5)
        assert result.depth == 0
        assert result.ast_nodes == []

    def test_function_complexity(self, python_project):
        result = analyze_file(str(python_project), "auth.py", depth=5)
        assert len(result.functions) >= 2
        for fn in result.functions:
            assert fn.cyclomatic_complexity >= 1
            assert fn.complexity_rating in ("low", "moderate", "high", "very-high")


# ---------------------------------------------------------------------------
# End-to-end: analyze_repo
# ---------------------------------------------------------------------------

class TestAnalyzeRepo:
    def test_discovers_files(self, python_project):
        result = analyze_repo(str(python_project), depth=3,
                              files=["auth.py", "utils.py"])
        assert isinstance(result, RepoAnalysis)
        assert len(result.files) == 2
        assert result.total_functions >= 4

    def test_hotspots(self, python_project):
        result = analyze_repo(str(python_project), depth=5,
                              files=["auth.py", "utils.py"])
        hotspots = result.hotspots
        assert len(hotspots) >= 1
        # Hotspots should be sorted by complexity (descending)
        for i in range(len(hotspots) - 1):
            assert hotspots[i].cyclomatic_complexity >= hotspots[i + 1].cyclomatic_complexity


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

class TestFormatters:
    def test_format_file_analysis(self, python_project):
        result = analyze_file(str(python_project), "auth.py", depth=5)
        text = format_analysis(result)
        assert "auth.py" in text
        assert "Layer 1: AST" in text
        assert "authenticate" in text

    def test_format_repo_analysis(self, python_project):
        result = analyze_repo(str(python_project), depth=5,
                              files=["auth.py", "utils.py"])
        text = format_analysis(result)
        assert "Repository Analysis" in text
        assert "Layer Summary" in text

    def test_json_output_file(self, python_project):
        result = analyze_file(str(python_project), "auth.py", depth=5)
        j = analysis_to_json(result)
        data = json.loads(j)
        assert data["file_path"] == "auth.py"
        assert data["language"] == "python"
        assert len(data["ast_nodes"]) >= 2

    def test_json_output_repo(self, python_project):
        result = analyze_repo(str(python_project), depth=5,
                              files=["auth.py", "utils.py"])
        j = analysis_to_json(result)
        data = json.loads(j)
        assert data["files_analyzed"] == 2
        assert data["total_functions"] >= 4


# ---------------------------------------------------------------------------
# Integration: real test against repoforge itself
# ---------------------------------------------------------------------------

class TestRealRepo:
    """Run against the actual repoforge codebase for integration validation."""

    def test_analyze_real_file(self):
        """Analyze repoforge/graph.py at depth 5 — should find real symbols."""
        repo_root = str(Path(__file__).resolve().parent.parent)
        result = analyze_file(repo_root, "repoforge/graph.py", depth=5)
        assert result.language == "python"
        names = [n.name for n in result.ast_nodes]
        assert "build_graph" in names
        assert "build_graph_v2" in names

    def test_analyze_real_file_has_cfg(self):
        """graph.py should have control flow nodes."""
        repo_root = str(Path(__file__).resolve().parent.parent)
        result = analyze_file(repo_root, "repoforge/graph.py", depth=5)
        assert len(result.cfg_nodes) > 0

    def test_analyze_real_file_has_calls(self):
        """graph.py should have call edges."""
        repo_root = str(Path(__file__).resolve().parent.parent)
        result = analyze_file(repo_root, "repoforge/graph.py", depth=5)
        assert len(result.call_edges) > 0
