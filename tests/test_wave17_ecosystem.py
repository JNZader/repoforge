"""Tests for Wave 17: Ecosystem — packaging, Docker, plugin registry."""

import json
from pathlib import Path

import pytest

from repoforge.ecosystem import (
    PluginInfo,
    get_available_extras,
    get_package_metadata,
    get_plugin_registry,
)

# ── Package metadata ─────────────────────────────────────────────────────


class TestPackageMetadata:

    def test_returns_dict(self):
        meta = get_package_metadata()
        assert isinstance(meta, dict)

    def test_has_name(self):
        meta = get_package_metadata()
        assert "name" in meta
        assert meta["name"] == "repoforge-ai"

    def test_has_version(self):
        meta = get_package_metadata()
        assert "version" in meta

    def test_has_description(self):
        meta = get_package_metadata()
        assert "description" in meta


class TestAvailableExtras:

    def test_returns_list(self):
        extras = get_available_extras()
        assert isinstance(extras, list)

    def test_includes_intelligence(self):
        extras = get_available_extras()
        names = [e["name"] for e in extras]
        assert "intelligence" in names

    def test_includes_dev(self):
        extras = get_available_extras()
        names = [e["name"] for e in extras]
        assert "dev" in names

    def test_each_extra_has_packages(self):
        extras = get_available_extras()
        for extra in extras:
            assert "name" in extra
            assert "packages" in extra
            assert isinstance(extra["packages"], list)


# ── Plugin registry ──────────────────────────────────────────────────────


class TestPluginRegistry:

    def test_returns_list(self):
        registry = get_plugin_registry()
        assert isinstance(registry, list)

    def test_includes_builtin_modules(self):
        registry = get_plugin_registry()
        names = [p.name for p in registry]
        assert "scoring" in names
        assert "cache" in names
        assert "renderers" in names

    def test_each_plugin_has_fields(self):
        registry = get_plugin_registry()
        for p in registry:
            assert isinstance(p, PluginInfo)
            assert p.name
            assert p.description
            assert p.module_path

    def test_serializable_to_json(self):
        registry = get_plugin_registry()
        data = [{"name": p.name, "description": p.description} for p in registry]
        serialized = json.dumps(data)
        assert isinstance(serialized, str)

    def test_no_duplicates(self):
        registry = get_plugin_registry()
        names = [p.name for p in registry]
        assert len(names) == len(set(names))
