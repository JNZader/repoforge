"""Clean-process contracts for optional package import surfaces."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap


def _run_clean_process(script: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_search_surface_when_faiss_is_missing() -> None:
    result = _run_clean_process(
        """
        import importlib
        import importlib.abc
        import json
        import sys

        class MissingFaiss(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "faiss":
                    raise ModuleNotFoundError("blocked optional dependency: faiss")
                return None

        sys.meta_path.insert(0, MissingFaiss())
        availability = importlib.import_module("repoforge.search._availability")
        search = importlib.import_module("repoforge.search")
        lazy_before = "repoforge.search.index" in sys.modules
        index = search.BM25Index()
        added = index.add(["authentication token"], ["auth"], ["symbol"])
        matches = index.search("authentication")
        lazy_class = search.SearchIndex.__name__

        print(json.dumps({
            "leaf_available": availability.SEARCH_AVAILABLE,
            "facade_available": search.SEARCH_AVAILABLE,
            "lazy_before": lazy_before,
            "lazy_class": lazy_class,
            "added": added,
            "match_ids": [match.entity_id for match in matches],
        }))
        """
    )

    assert result == {
        "leaf_available": False,
        "facade_available": False,
        "lazy_before": False,
        "lazy_class": "SearchIndex",
        "added": 1,
        "match_ids": ["auth"],
    }


def test_search_surface_when_faiss_is_available() -> None:
    result = _run_clean_process(
        """
        import importlib
        import json
        import sys
        import types

        sys.modules["faiss"] = types.ModuleType("faiss")
        availability = importlib.import_module("repoforge.search._availability")
        search = importlib.import_module("repoforge.search")

        print(json.dumps({
            "leaf_available": availability.SEARCH_AVAILABLE,
            "facade_available": search.SEARCH_AVAILABLE,
            "pure_export": search.BM25Index.__name__,
            "lazy_index_loaded": "repoforge.search.index" in sys.modules,
        }))
        """
    )

    assert result == {
        "leaf_available": True,
        "facade_available": True,
        "pure_export": "BM25Index",
        "lazy_index_loaded": False,
    }


def test_intelligence_surface_when_tree_sitter_is_missing() -> None:
    result = _run_clean_process(
        """
        import importlib
        import importlib.abc
        import json
        from pathlib import Path
        import sys

        class MissingTreeSitter(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "tree_sitter" or fullname.startswith("tree_sitter."):
                    raise ModuleNotFoundError("blocked optional dependency: tree_sitter")
                return None

        sys.meta_path.insert(0, MissingTreeSitter())
        availability = importlib.import_module("repoforge.intelligence._availability")
        intelligence = importlib.import_module("repoforge.intelligence")
        compressor = importlib.import_module("repoforge.intelligence.compressor")
        registry = importlib.import_module("repoforge.intelligence.extractor_registry")

        print(json.dumps({
            "leaf_available": availability.INTELLIGENCE_AVAILABLE,
            "facade_available": intelligence.INTELLIGENCE_AVAILABLE,
            "build_export": intelligence.BuildInfo.__name__,
            "registry": registry.get_ast_registry(),
            "compressor_back_edge": "from . import INTELLIGENCE_AVAILABLE" in Path(compressor.__file__).read_text(),
            "registry_back_edge": "from . import INTELLIGENCE_AVAILABLE" in Path(registry.__file__).read_text(),
        }))
        """
    )

    assert result == {
        "leaf_available": False,
        "facade_available": False,
        "build_export": "BuildInfo",
        "registry": None,
        "compressor_back_edge": False,
        "registry_back_edge": False,
    }


def test_intelligence_surface_when_tree_sitter_is_available() -> None:
    result = _run_clean_process(
        """
        import importlib
        import json
        import sys
        import types

        sys.modules["tree_sitter"] = types.ModuleType("tree_sitter")
        availability = importlib.import_module("repoforge.intelligence._availability")
        intelligence = importlib.import_module("repoforge.intelligence")

        print(json.dumps({
            "leaf_available": availability.INTELLIGENCE_AVAILABLE,
            "facade_available": intelligence.INTELLIGENCE_AVAILABLE,
            "symbol_export": intelligence.ASTSymbol.__name__,
            "build_export": intelligence.BuildInfo.__name__,
        }))
        """
    )

    assert result == {
        "leaf_available": True,
        "facade_available": True,
        "symbol_export": "ASTSymbol",
        "build_export": "BuildInfo",
    }


def test_search_and_intelligence_fallbacks_coexist() -> None:
    result = _run_clean_process(
        """
        import importlib
        import importlib.abc
        import json
        import sys

        class MissingExtras(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "faiss" or fullname == "tree_sitter" or fullname.startswith("tree_sitter."):
                    raise ModuleNotFoundError(f"blocked optional dependency: {fullname}")
                return None

        sys.meta_path.insert(0, MissingExtras())
        search = importlib.import_module("repoforge.search")
        intelligence = importlib.import_module("repoforge.intelligence")

        print(json.dumps({
            "search_available": search.SEARCH_AVAILABLE,
            "intelligence_available": intelligence.INTELLIGENCE_AVAILABLE,
            "bm25_export": search.BM25Index.__name__,
            "build_export": intelligence.BuildInfo.__name__,
        }))
        """
    )

    assert result == {
        "search_available": False,
        "intelligence_available": False,
        "bm25_export": "BM25Index",
        "build_export": "BuildInfo",
    }
