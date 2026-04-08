"""IR types for scanner/repo-map output.

Typed replacements for the dict returned by ``scanner.scan_repo()``.
All types are frozen (immutable) to prevent accidental mutation
between pipeline stages.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Leaf types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ModuleInfo:
    """A single source file discovered by the scanner."""

    path: str
    """Relative path from repo root."""

    name: str
    """Filename or short identifier."""

    language: str
    """Detected programming language."""

    exports: list[str] = field(default_factory=list)
    """Public symbols exported by this module."""

    imports: list[str] = field(default_factory=list)
    """External dependencies imported."""

    summary_hint: str = ""
    """Short description from docstring/comments."""

    # -- dict-compat bridge (Phase 2 migration) --

    def get(self, key: str, default=None):
        """Allow ``module.get("path")`` while consumers migrate."""
        return self.to_dict().get(key, default)

    def __getitem__(self, key: str):
        d = self.to_dict()
        return d[key]

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "name": self.name,
            "language": self.language,
            "exports": list(self.exports),
            "imports": list(self.imports),
            "summary_hint": self.summary_hint,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ModuleInfo:
        return cls(
            path=d["path"],
            name=d["name"],
            language=d["language"],
            exports=list(d.get("exports", [])),
            imports=list(d.get("imports", [])),
            summary_hint=d.get("summary_hint", ""),
        )


@dataclass(frozen=True, slots=True)
class LayerInfo:
    """A logical layer (e.g. 'backend', 'frontend') in the repo."""

    path: str
    """Root directory of the layer, relative to repo root."""

    modules: list[ModuleInfo] = field(default_factory=list)
    """Source files belonging to this layer."""

    # -- dict-compat bridge (Phase 2 migration) --

    def get(self, key: str, default=None):
        """Allow ``layer.get("modules")`` while consumers migrate."""
        return self.to_dict().get(key, default)

    def __getitem__(self, key: str):
        d = self.to_dict()
        return d[key]

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "modules": [m.to_dict() for m in self.modules],
        }

    @classmethod
    def from_dict(cls, d: dict) -> LayerInfo:
        return cls(
            path=d["path"],
            modules=[ModuleInfo.from_dict(m) for m in d.get("modules", [])],
        )


@dataclass(frozen=True, slots=True)
class TechStack:
    """Detected technology stack."""

    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "languages": list(self.languages),
            "frameworks": list(self.frameworks),
        }

    @classmethod
    def from_dict(cls, d: dict) -> TechStack:
        return cls(
            languages=list(d.get("languages", [])),
            frameworks=list(d.get("frameworks", [])),
        )


@dataclass(frozen=True, slots=True)
class BuildMetadata:
    """Metadata extracted from build/manifest files (go.mod, Cargo.toml, etc.)."""

    language: str = ""
    module_path: str = ""
    version: str = ""
    go_version: str = ""

    def to_dict(self) -> dict:
        d: dict = {}
        if self.language:
            d["language"] = self.language
        if self.module_path:
            d["module_path"] = self.module_path
        if self.version:
            d["version"] = self.version
        if self.go_version:
            d["go_version"] = self.go_version
        return d

    @classmethod
    def from_dict(cls, d: dict) -> BuildMetadata:
        return cls(
            language=d.get("language", ""),
            module_path=d.get("module_path", ""),
            version=d.get("version", ""),
            go_version=d.get("go_version", ""),
        )


# ---------------------------------------------------------------------------
# Root aggregate
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RepoMap:
    """Typed representation of scanner.scan_repo() output.

    Replaces the raw dict that was previously passed between pipeline
    stages. All nested structures use typed dataclasses.
    """

    root: str
    tech_stack: list[str]
    layers: dict[str, LayerInfo]
    entry_points: list[str]
    config_files: list[str]
    repoforge_config: dict
    stats: dict
    all_directories: list[str] = field(default_factory=list)
    build_info: BuildMetadata | None = None

    # -- dict-compat bridge (Phase 2 migration) --
    # Allows ``repo_map["layers"]`` and ``repo_map.get("stats", {})``
    # so downstream consumers keep working until Phase 3 migrates them.

    def get(self, key: str, default=None):
        """Allow ``repo_map.get("layers")`` while consumers migrate."""
        return self.to_dict().get(key, default)

    def __getitem__(self, key: str):
        d = self.to_dict()
        return d[key]

    def __contains__(self, key: str) -> bool:
        return key in self.to_dict()

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def items(self):
        return self.to_dict().items()

    def to_dict(self) -> dict:
        result: dict = {
            "root": self.root,
            "tech_stack": list(self.tech_stack),
            "layers": {k: v.to_dict() for k, v in self.layers.items()},
            "entry_points": list(self.entry_points),
            "config_files": list(self.config_files),
            "repoforge_config": dict(self.repoforge_config),
            "stats": dict(self.stats),
            "_all_directories": list(self.all_directories),
        }
        if self.build_info is not None:
            result["build_info"] = self.build_info.to_dict()
        return result

    @classmethod
    def from_dict(cls, d: dict) -> RepoMap:
        raw_layers = d.get("layers", {})
        layers: dict[str, LayerInfo] = {}
        for name, layer_data in raw_layers.items():
            if isinstance(layer_data, dict):
                layers[name] = LayerInfo.from_dict(layer_data)
            else:
                layers[name] = layer_data  # already a LayerInfo

        build_raw = d.get("build_info")
        build_info: BuildMetadata | None = None
        if isinstance(build_raw, dict):
            build_info = BuildMetadata.from_dict(build_raw)
        elif isinstance(build_raw, BuildMetadata):
            build_info = build_raw

        return cls(
            root=d.get("root", ""),
            tech_stack=list(d.get("tech_stack", [])),
            layers=layers,
            entry_points=list(d.get("entry_points", [])),
            config_files=list(d.get("config_files", [])),
            repoforge_config=dict(d.get("repoforge_config", {})),
            stats=dict(d.get("stats", {})),
            all_directories=list(d.get("_all_directories", d.get("all_directories", []))),
            build_info=build_info,
        )
