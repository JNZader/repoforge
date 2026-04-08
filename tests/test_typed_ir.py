"""Tests for typed IR dataclasses (Phase 1: Foundation).

Covers round-trip serialization, frozen immutability, from_dict with
missing optional fields, and ContextBundle mutability.
"""

from dataclasses import FrozenInstanceError

import pytest

from repoforge.ir.context import ContextBundle
from repoforge.ir.extraction import APIEndpoint, DependencyEdge, SymbolRef
from repoforge.ir.repo import (
    BuildMetadata,
    LayerInfo,
    ModuleInfo,
    RepoMap,
    TechStack,
)

# ── ModuleInfo ──────────────────────────────────────────────────────────────


class TestModuleInfo:

    def test_round_trip(self):
        mi = ModuleInfo(
            path="src/main.py",
            name="main.py",
            language="python",
            exports=["main", "cli"],
            imports=["click", "pathlib"],
            summary_hint="CLI entry point",
        )
        assert ModuleInfo.from_dict(mi.to_dict()) == mi

    def test_frozen(self):
        mi = ModuleInfo(path="a.py", name="a", language="python")
        with pytest.raises(FrozenInstanceError):
            mi.path = "b.py"  # type: ignore[misc]

    def test_from_dict_missing_optionals(self):
        mi = ModuleInfo.from_dict({"path": "a.py", "name": "a", "language": "python"})
        assert mi.exports == []
        assert mi.imports == []
        assert mi.summary_hint == ""

    def test_to_dict_keys(self):
        mi = ModuleInfo(path="a.py", name="a", language="python")
        d = mi.to_dict()
        assert set(d.keys()) == {"path", "name", "language", "exports", "imports", "summary_hint"}


# ── LayerInfo ───────────────────────────────────────────────────────────────


class TestLayerInfo:

    def test_round_trip(self):
        li = LayerInfo(
            path="src/",
            modules=[
                ModuleInfo(path="src/app.py", name="app.py", language="python"),
            ],
        )
        assert LayerInfo.from_dict(li.to_dict()) == li

    def test_frozen(self):
        li = LayerInfo(path="src/")
        with pytest.raises(FrozenInstanceError):
            li.path = "lib/"  # type: ignore[misc]

    def test_from_dict_empty_modules(self):
        li = LayerInfo.from_dict({"path": "src/"})
        assert li.modules == []

    def test_nested_modules_are_typed(self):
        li = LayerInfo.from_dict({
            "path": "src/",
            "modules": [{"path": "a.py", "name": "a", "language": "go"}],
        })
        assert isinstance(li.modules[0], ModuleInfo)


# ── TechStack ───────────────────────────────────────────────────────────────


class TestTechStack:

    def test_round_trip(self):
        ts = TechStack(languages=["python", "go"], frameworks=["django"])
        assert TechStack.from_dict(ts.to_dict()) == ts

    def test_frozen(self):
        ts = TechStack()
        with pytest.raises(FrozenInstanceError):
            ts.languages = ["rust"]  # type: ignore[misc]

    def test_defaults(self):
        ts = TechStack.from_dict({})
        assert ts.languages == []
        assert ts.frameworks == []


# ── BuildMetadata ───────────────────────────────────────────────────────────


class TestBuildMetadata:

    def test_round_trip(self):
        bm = BuildMetadata(language="go", module_path="github.com/x/y", go_version="1.21")
        assert BuildMetadata.from_dict(bm.to_dict()) == bm

    def test_to_dict_omits_empty(self):
        bm = BuildMetadata()
        assert bm.to_dict() == {}

    def test_to_dict_partial(self):
        bm = BuildMetadata(language="rust", version="0.1.0")
        d = bm.to_dict()
        assert d == {"language": "rust", "version": "0.1.0"}
        assert "module_path" not in d
        assert "go_version" not in d

    def test_frozen(self):
        bm = BuildMetadata(language="go")
        with pytest.raises(FrozenInstanceError):
            bm.language = "rust"  # type: ignore[misc]


# ── RepoMap ─────────────────────────────────────────────────────────────────


class TestRepoMap:

    @staticmethod
    def _sample_dict() -> dict:
        """Mimics scanner.scan_repo() output structure."""
        return {
            "root": "/tmp/repo",
            "tech_stack": ["python", "typescript"],
            "layers": {
                "main": {
                    "path": "src/",
                    "modules": [
                        {"path": "src/app.py", "name": "app.py", "language": "python"},
                    ],
                },
            },
            "entry_points": ["src/app.py"],
            "config_files": ["pyproject.toml"],
            "repoforge_config": {"max_files_per_layer": 500},
            "stats": {"total_files": 42, "rg_available": True},
            "_all_directories": ["src/", "tests/"],
            "build_info": {"language": "python", "version": "1.0.0"},
        }

    def test_round_trip(self):
        d = self._sample_dict()
        rm = RepoMap.from_dict(d)
        reconstructed = RepoMap.from_dict(rm.to_dict())
        assert reconstructed == rm

    def test_from_dict_creates_typed_layers(self):
        rm = RepoMap.from_dict(self._sample_dict())
        assert isinstance(rm.layers["main"], LayerInfo)
        assert isinstance(rm.layers["main"].modules[0], ModuleInfo)

    def test_from_dict_creates_typed_build_info(self):
        rm = RepoMap.from_dict(self._sample_dict())
        assert isinstance(rm.build_info, BuildMetadata)
        assert rm.build_info.language == "python"

    def test_from_dict_no_build_info(self):
        d = self._sample_dict()
        del d["build_info"]
        rm = RepoMap.from_dict(d)
        assert rm.build_info is None

    def test_frozen(self):
        rm = RepoMap.from_dict(self._sample_dict())
        with pytest.raises(FrozenInstanceError):
            rm.root = "/other"  # type: ignore[misc]

    def test_to_dict_maps_all_directories(self):
        rm = RepoMap.from_dict(self._sample_dict())
        d = rm.to_dict()
        assert d["_all_directories"] == ["src/", "tests/"]

    def test_from_dict_all_directories_alias(self):
        """Accepts both _all_directories and all_directories keys."""
        d = self._sample_dict()
        d["all_directories"] = d.pop("_all_directories")
        rm = RepoMap.from_dict(d)
        assert rm.all_directories == ["src/", "tests/"]


# ── ContextBundle ───────────────────────────────────────────────────────────


class TestContextBundle:

    def test_mutable(self):
        cb = ContextBundle()
        cb.graph_ctx = "graph data"
        cb.semantic_ctx = "semantic data"
        assert cb.graph_ctx == "graph data"

    def test_to_dict_excludes_private(self):
        cb = ContextBundle()
        cb._graph = object()
        cb._facts = [1, 2, 3]
        cb._all_files = ["a.py"]
        d = cb.to_dict()
        assert "_graph" not in d
        assert "_facts" not in d
        assert "_all_files" not in d

    def test_to_dict_includes_public(self):
        cb = ContextBundle(graph_ctx="g", semantic_ctx="s", dep_health_ctx="dh")
        d = cb.to_dict()
        assert d["graph_ctx"] == "g"
        assert d["semantic_ctx"] == "s"
        assert d["dep_health_ctx"] == "dh"

    def test_from_dict_round_trip(self):
        cb = ContextBundle(
            graph_ctx="g",
            short_graph_ctx="sg",
            diagram_ctx="diag",
            semantic_ctx="sem",
            facts_ctx="facts",
            api_surface_ctx="api",
            doc_chunks={"ch1": "data"},
            fo_context_by_chapter={"ch1": "fo"},
            dep_health_ctx="dh",
            coverage_ctx="cov",
        )
        restored = ContextBundle.from_dict(cb.to_dict())
        assert restored.to_dict() == cb.to_dict()

    def test_from_dict_missing_fields(self):
        cb = ContextBundle.from_dict({})
        assert cb.graph_ctx == ""
        assert cb.doc_chunks == {}
        assert cb.fo_context_by_chapter is None

    def test_from_dict_does_not_restore_private(self):
        cb = ContextBundle.from_dict({"graph_ctx": "g"})
        assert cb._graph is None
        assert cb._facts == []
        assert cb._all_files == []


# ── APIEndpoint ─────────────────────────────────────────────────────────────


class TestAPIEndpoint:

    def test_round_trip(self):
        ep = APIEndpoint(method="GET", path="/api/users", file="routes.py", line=42, handler="list_users")
        assert APIEndpoint.from_dict(ep.to_dict()) == ep

    def test_frozen(self):
        ep = APIEndpoint(method="POST", path="/api", file="r.py", line=1)
        with pytest.raises(FrozenInstanceError):
            ep.method = "PUT"  # type: ignore[misc]

    def test_from_dict_defaults(self):
        ep = APIEndpoint.from_dict({"method": "GET", "path": "/", "file": "a.py"})
        assert ep.line == 0
        assert ep.handler == ""


# ── DependencyEdge ──────────────────────────────────────────────────────────


class TestDependencyEdge:

    def test_round_trip(self):
        edge = DependencyEdge(source="a.py", target="b.py", kind="imports")
        assert DependencyEdge.from_dict(edge.to_dict()) == edge

    def test_frozen(self):
        edge = DependencyEdge(source="a.py", target="b.py")
        with pytest.raises(FrozenInstanceError):
            edge.source = "c.py"  # type: ignore[misc]

    def test_default_kind(self):
        edge = DependencyEdge.from_dict({"source": "a.py", "target": "b.py"})
        assert edge.kind == "imports"


# ── SymbolRef ───────────────────────────────────────────────────────────────


class TestSymbolRef:

    def test_round_trip(self):
        sym = SymbolRef(name="User", file="models.py", line=10, kind="class")
        assert SymbolRef.from_dict(sym.to_dict()) == sym

    def test_frozen(self):
        sym = SymbolRef(name="foo", file="a.py", line=1)
        with pytest.raises(FrozenInstanceError):
            sym.name = "bar"  # type: ignore[misc]

    def test_default_kind(self):
        sym = SymbolRef.from_dict({"name": "foo", "file": "a.py", "line": 5})
        assert sym.kind == "function"

    def test_to_dict_keys(self):
        sym = SymbolRef(name="X", file="x.py", line=1, kind="class")
        assert set(sym.to_dict().keys()) == {"name", "file", "line", "kind"}


# ── Backward-compatible imports ─────────────────────────────────────────────


class TestBackwardCompatImports:
    """Verify that the old import path still works after package promotion."""

    def test_chapterspec_importable(self):
        from repoforge.ir import ChapterSpec
        assert ChapterSpec is not None

    def test_generatedchapter_importable(self):
        from repoforge.ir import GeneratedChapter
        assert GeneratedChapter is not None

    def test_documentationresult_importable(self):
        from repoforge.ir import DocumentationResult
        assert DocumentationResult is not None

    def test_all_new_types_importable(self):
        from repoforge.ir import (
            APIEndpoint,
            BuildMetadata,
            ContextBundle,
            DependencyEdge,
            LayerInfo,
            ModuleInfo,
            RepoMap,
            SymbolRef,
            TechStack,
        )
        for cls in [RepoMap, LayerInfo, ModuleInfo, TechStack, BuildMetadata,
                     ContextBundle, APIEndpoint, DependencyEdge, SymbolRef]:
            assert cls is not None
