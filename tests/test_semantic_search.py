"""
tests/test_semantic_search.py — Tests for behavior-based semantic search.

Tests cover:
- BehaviorDescriptor construction
- BM25 tokenizer (camelCase/snake_case splitting)
- BehaviorIndex building and search
- search_repo() end-to-end
- Formatters (text and JSON)
- Real repo integration test
"""

import json
from pathlib import Path

import pytest

from repoforge.deep_analysis import ASTNode, CallEdgeInfo, CFGNode, DFGEdge
from repoforge.semantic_search import (
    _BM25,
    BehaviorIndex,
    BehaviorMatch,
    _build_call_text,
    _build_flow_text,
    _build_param_text,
    _build_signature,
    _tokenize,
    build_behavior_index,
    format_search_results,
    search_repo,
    search_results_to_json,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def python_project(tmp_path):
    """Create a temporary Python project with searchable code."""
    (tmp_path / "auth.py").write_text("""\
def authenticate_user(token, secret):
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


def validate_permissions(user, resource):
    if user.role == "admin":
        return True
    for permission in user.permissions:
        if permission.resource == resource:
            return permission.allowed
    return False
""")

    (tmp_path / "data.py").write_text("""\
def process_batch(items, batch_size=100):
    results = []
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        processed = transform_batch(batch)
        results.extend(processed)
    return results


def transform_batch(batch):
    output = []
    for item in batch:
        if item.valid:
            transformed = apply_transform(item)
            output.append(transformed)
    return output


def upload_file(file_path, destination):
    content = read_file(file_path)
    if not content:
        raise FileNotFoundError(f"Empty: {file_path}")
    compressed = compress(content)
    result = send_to_storage(compressed, destination)
    return result
""")

    return tmp_path


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class TestTokenizer:
    def test_snake_case_split(self):
        tokens = _tokenize("authenticate_user")
        assert "authenticate" in tokens
        assert "user" in tokens

    def test_camel_case_split(self):
        tokens = _tokenize("authenticateUser")
        assert "authenticate" in tokens
        assert "user" in tokens

    def test_mixed_case(self):
        tokens = _tokenize("processHTTPRequest")
        tokens_lower = [t.lower() for t in tokens]
        assert "process" in tokens_lower
        assert "http" in tokens_lower or "httprequest" in tokens_lower

    def test_punctuation_removed(self):
        tokens = _tokenize("foo.bar(baz)")
        assert "foo" in tokens
        assert "bar" in tokens
        assert "baz" in tokens


# ---------------------------------------------------------------------------
# BM25 engine
# ---------------------------------------------------------------------------

class TestBM25:
    def test_basic_search(self):
        bm25 = _BM25()
        bm25.add(
            texts=[
                "authenticate user with JWT token",
                "process batch of items in parallel",
                "upload file to cloud storage",
            ],
            ids=["auth", "batch", "upload"],
        )
        results = bm25.search("authentication JWT")
        assert len(results) >= 1
        assert results[0][0] == "auth"

    def test_empty_query(self):
        bm25 = _BM25()
        bm25.add(texts=["some text"], ids=["a"])
        results = bm25.search("")
        assert results == []

    def test_no_match(self):
        bm25 = _BM25()
        bm25.add(texts=["hello world"], ids=["a"])
        results = bm25.search("xyzzy quantum")
        assert results == []

    def test_size(self):
        bm25 = _BM25()
        bm25.add(texts=["a", "b", "c"], ids=["1", "2", "3"])
        assert bm25.size == 3


# ---------------------------------------------------------------------------
# Descriptor builders
# ---------------------------------------------------------------------------

class TestDescriptorBuilders:
    def test_build_signature(self):
        node = ASTNode(name="foo", kind="function", file="f.py",
                       line=1, end_line=5, params=["x: int", "y: str"])
        sig = _build_signature(node)
        assert sig == "foo(x: int, y: str)"

    def test_build_param_text(self):
        text = _build_param_text(["token: str", "secret: bytes"])
        assert "token" in text
        assert "str" in text

    def test_build_param_text_empty(self):
        assert _build_param_text([]) == ""

    def test_build_call_text(self):
        edges = [
            CallEdgeInfo(caller="a", callee="validate", file="f.py", line=1),
            CallEdgeInfo(caller="a", callee="save", file="f.py", line=2),
        ]
        text = _build_call_text(edges)
        assert "validate" in text
        assert "save" in text

    def test_build_call_text_empty(self):
        assert _build_call_text([]) == ""

    def test_build_flow_text(self):
        nodes = [
            CFGNode(node_type="branch", label="if x", file="f.py",
                    line=1, parent_function="fn"),
            CFGNode(node_type="loop", label="for item", file="f.py",
                    line=2, parent_function="fn"),
        ]
        text = _build_flow_text(nodes)
        assert "branch" in text
        assert "loop" in text

    def test_build_flow_text_empty(self):
        assert _build_flow_text([]) == ""


# ---------------------------------------------------------------------------
# BehaviorIndex
# ---------------------------------------------------------------------------

class TestBehaviorIndex:
    def test_build_index(self, python_project):
        index = build_behavior_index(str(python_project), depth=3,
                                     files=["auth.py", "data.py"])
        assert index.size >= 5  # at least 5 functions

    def test_search_authentication(self, python_project):
        index = build_behavior_index(str(python_project), depth=3,
                                     files=["auth.py", "data.py"])
        results = index.search("authenticate user token")
        assert len(results) >= 1
        # The top result should be auth-related
        top_names = [r.function_name for r in results[:3]]
        assert any("auth" in name.lower() for name in top_names)

    def test_search_batch_processing(self, python_project):
        index = build_behavior_index(str(python_project), depth=3,
                                     files=["auth.py", "data.py"])
        results = index.search("process batch items")
        assert len(results) >= 1
        top_names = [r.function_name for r in results[:3]]
        assert any("batch" in name.lower() or "process" in name.lower()
                    for name in top_names)

    def test_search_file_upload(self, python_project):
        index = build_behavior_index(str(python_project), depth=3,
                                     files=["auth.py", "data.py"])
        results = index.search("upload file storage")
        assert len(results) >= 1
        top_names = [r.function_name for r in results[:3]]
        assert any("upload" in name.lower() for name in top_names)

    def test_empty_index(self, tmp_path):
        (tmp_path / "empty.py").write_text("# nothing here\n")
        index = build_behavior_index(str(tmp_path), depth=3,
                                     files=["empty.py"])
        results = index.search("anything")
        assert results == []


# ---------------------------------------------------------------------------
# search_repo (convenience function)
# ---------------------------------------------------------------------------

class TestSearchRepo:
    def test_search_repo_convenience(self, python_project):
        results = search_repo(
            str(python_project), "validate permissions",
            depth=3, top_k=5, files=["auth.py", "data.py"],
        )
        assert len(results) >= 1
        assert all(isinstance(r, BehaviorMatch) for r in results)

    def test_top_k_limit(self, python_project):
        results = search_repo(
            str(python_project), "function",
            depth=2, top_k=2, files=["auth.py", "data.py"],
        )
        assert len(results) <= 2


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

class TestFormatters:
    def test_format_results(self, python_project):
        results = search_repo(
            str(python_project), "authenticate token",
            depth=3, top_k=3, files=["auth.py", "data.py"],
        )
        text = format_search_results(results)
        assert "Behavior Search Results" in text
        assert "score:" in text

    def test_format_empty_results(self):
        text = format_search_results([])
        assert "No matching" in text

    def test_json_output(self, python_project):
        results = search_repo(
            str(python_project), "batch process",
            depth=3, top_k=3, files=["auth.py", "data.py"],
        )
        j = search_results_to_json(results)
        data = json.loads(j)
        assert "count" in data
        assert "results" in data
        assert isinstance(data["results"], list)


# ---------------------------------------------------------------------------
# Integration: real test against repoforge itself
# ---------------------------------------------------------------------------

class TestRealRepo:
    """Run against the actual repoforge codebase for integration validation."""

    def test_search_real_repo(self):
        """Search repoforge for graph-building functions."""
        repo_root = str(Path(__file__).resolve().parent.parent)
        results = search_repo(
            repo_root, "build dependency graph",
            depth=3, top_k=10,
            files=["repoforge/graph.py"],
        )
        assert len(results) >= 1
        func_names = [r.function_name for r in results]
        assert any("graph" in name.lower() or "build" in name.lower()
                    for name in func_names)

    def test_search_real_repo_blast_radius(self):
        """Search for blast radius related functions."""
        repo_root = str(Path(__file__).resolve().parent.parent)
        results = search_repo(
            repo_root, "blast radius affected files",
            depth=3, top_k=10,
            files=["repoforge/blast_radius.py"],
        )
        assert len(results) >= 1
        func_names = [r.function_name for r in results]
        assert any("blast" in name.lower() or "radius" in name.lower()
                    or "compute" in name.lower()
                    for name in func_names)
