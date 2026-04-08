"""YAML-based chapter template loader and condition evaluator.

Replaces hardcoded ``ADAPTIVE_CHAPTERS`` with declarative YAML templates.
Each project type gets its own YAML file under ``repoforge/templates/``.
Users can add custom templates via ``repoforge.yaml`` ``templates:`` key.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from .ir.repo import RepoMap

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TemplateValidationError(Exception):
    """Raised when a template YAML file fails schema validation."""


class ConditionError(Exception):
    """Raised when a condition expression is invalid or unsafe."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

KNOWN_PROJECT_TYPES = frozenset({
    "web_service",
    "cli_tool",
    "library_sdk",
    "data_science",
    "frontend_app",
    "mobile_app",
    "desktop_app",
    "infra_devops",
    "monorepo",
    "generic",
})

# Valid prompt_keys — chapter files handled by _dispatch_prompt in chapters.py
VALID_PROMPT_KEYS = frozenset({
    "index",
    "overview",
    "quickstart",
    "architecture",
    "core_mechanisms",
    "data_models",
    "api_reference",
    "dev_guide",
})


@dataclass(frozen=True, slots=True)
class ChapterDef:
    """A single chapter entry within a project-type template."""

    file: str
    title: str
    description: str
    prompt_key: str | None = None
    prompt_template: str | None = None
    condition: str | None = None
    order: int = 0


@dataclass(frozen=True, slots=True)
class ChapterTemplate:
    """A complete project-type template with its chapter list."""

    name: str
    project_type: str
    chapters: tuple[ChapterDef, ...] = field(default_factory=tuple)

    @property
    def chapter_list(self) -> list[ChapterDef]:
        """Return chapters as a mutable list for compatibility."""
        return list(self.chapters)


# ---------------------------------------------------------------------------
# ConditionEvaluator
# ---------------------------------------------------------------------------

# Regex patterns for parsing condition expressions
_FUNC_RE = re.compile(
    r"""
    (has_tech|has_config|has_path_match|has_layer)  # function name
    \(\s*                                           # open paren
    ['"]([^'"]+)['"]                                # quoted string arg
    \s*\)                                           # close paren
    """,
    re.VERBOSE,
)

_COMPARE_RE = re.compile(
    r"""
    (layer_count|total_files)   # field name
    \s*(>=|<=|>|<|==|!=)\s*     # operator
    (\d+)                       # numeric value
    """,
    re.VERBOSE,
)


class ConditionEvaluator:
    """Evaluate condition expressions against a RepoMap.

    Supported predicates:
    - ``has_tech('name')`` — name in repo_map.tech_stack (case-insensitive)
    - ``has_config('name')`` — name in repo_map.config_files (substring)
    - ``has_path_match('glob')`` — fnmatch against any module path
    - ``has_layer('name')`` — name in repo_map.layers keys
    - ``layer_count <op> <int>`` — compare len(layers)
    - ``total_files <op> <int>`` — compare stats["total_files"]

    Boolean operators: ``and``, ``or`` (evaluated left-to-right, no precedence).
    NO ``eval()``.
    """

    @staticmethod
    def evaluate(condition: str, repo_map: RepoMap) -> bool:
        """Evaluate a condition string against the given RepoMap.

        Returns True if condition is None or empty.
        Raises ConditionError for invalid expressions.
        """
        if not condition or not condition.strip():
            return True

        expr = condition.strip()
        return ConditionEvaluator._eval_expr(expr, repo_map)

    @staticmethod
    def _eval_expr(expr: str, repo_map: RepoMap) -> bool:
        """Parse and evaluate a boolean expression with and/or."""
        # Split on ' or ' first (lowest precedence)
        or_parts = re.split(r"\s+or\s+", expr)
        if len(or_parts) > 1:
            return any(
                ConditionEvaluator._eval_expr(part.strip(), repo_map)
                for part in or_parts
            )

        # Split on ' and '
        and_parts = re.split(r"\s+and\s+", expr)
        if len(and_parts) > 1:
            return all(
                ConditionEvaluator._eval_expr(part.strip(), repo_map)
                for part in and_parts
            )

        # Single predicate
        return ConditionEvaluator._eval_predicate(expr.strip(), repo_map)

    @staticmethod
    def _eval_predicate(pred: str, repo_map: RepoMap) -> bool:
        """Evaluate a single predicate."""
        # Try function call: has_tech('x'), has_config('x'), etc.
        func_match = _FUNC_RE.fullmatch(pred)
        if func_match:
            func_name = func_match.group(1)
            arg = func_match.group(2)

            if func_name == "has_tech":
                return ConditionEvaluator._has_tech(arg, repo_map)
            if func_name == "has_config":
                return ConditionEvaluator._has_config(arg, repo_map)
            if func_name == "has_path_match":
                return ConditionEvaluator._has_path_match(arg, repo_map)
            if func_name == "has_layer":
                return ConditionEvaluator._has_layer(arg, repo_map)

        # Try comparison: layer_count >= 3, total_files > 100
        cmp_match = _COMPARE_RE.fullmatch(pred)
        if cmp_match:
            field_name = cmp_match.group(1)
            op = cmp_match.group(2)
            value = int(cmp_match.group(3))

            if field_name == "layer_count":
                actual = len(repo_map.layers)
            elif field_name == "total_files":
                actual = repo_map.stats.get("total_files", 0)
            else:  # pragma: no cover
                msg = f"Unknown field: {field_name}"
                raise ConditionError(msg)

            return ConditionEvaluator._compare(actual, op, value)

        msg = f"Invalid condition expression: {pred!r}"
        raise ConditionError(msg)

    @staticmethod
    def _has_tech(name: str, repo_map: RepoMap) -> bool:
        needle = name.lower()
        return any(needle in t.lower() for t in repo_map.tech_stack)

    @staticmethod
    def _has_config(name: str, repo_map: RepoMap) -> bool:
        needle = name.lower()
        return any(needle in c.lower() for c in repo_map.config_files)

    @staticmethod
    def _has_path_match(pattern: str, repo_map: RepoMap) -> bool:
        for layer in repo_map.layers.values():
            for mod in layer.modules:
                if fnmatch.fnmatch(mod.path.lower(), pattern.lower()):
                    return True
        return False

    @staticmethod
    def _has_layer(name: str, repo_map: RepoMap) -> bool:
        return name in repo_map.layers

    @staticmethod
    def _compare(actual: int, op: str, value: int) -> bool:
        ops = {
            ">=": actual >= value,
            "<=": actual <= value,
            ">": actual > value,
            "<": actual < value,
            "==": actual == value,
            "!=": actual != value,
        }
        return ops[op]


# ---------------------------------------------------------------------------
# TemplateLoader
# ---------------------------------------------------------------------------

_BUILTIN_DIR = Path(__file__).parent / "templates"

# Module-level cache: project_type -> ChapterTemplate
_CACHE: dict[str, ChapterTemplate] = {}


class TemplateLoader:
    """Discovers, validates, and caches YAML chapter templates.

    Built-in templates live in ``repoforge/templates/``.
    User templates override built-in ones when ``project_type`` matches.
    """

    def __init__(self, extra_dirs: list[Path] | None = None) -> None:
        self._extra_dirs: list[Path] = list(extra_dirs or [])
        self._loaded = False

    def discover(self) -> list[Path]:
        """Find all YAML template files from built-in + user directories."""
        paths: list[Path] = []

        if _BUILTIN_DIR.is_dir():
            paths.extend(sorted(_BUILTIN_DIR.glob("*.yaml")))
            paths.extend(sorted(_BUILTIN_DIR.glob("*.yml")))

        for d in self._extra_dirs:
            if d.is_dir():
                paths.extend(sorted(d.glob("*.yaml")))
                paths.extend(sorted(d.glob("*.yml")))

        return paths

    def load_all(self) -> None:
        """Discover, validate, and cache all templates.

        User templates override built-in templates for the same project_type.
        """
        if self._loaded:
            return

        # Load built-in first
        builtin_paths: list[Path] = []
        if _BUILTIN_DIR.is_dir():
            builtin_paths.extend(sorted(_BUILTIN_DIR.glob("*.yaml")))
            builtin_paths.extend(sorted(_BUILTIN_DIR.glob("*.yml")))

        for p in builtin_paths:
            tpl = self._load_file(p)
            _CACHE[tpl.project_type] = tpl

        # User templates override
        for d in self._extra_dirs:
            if d.is_dir():
                for p in sorted(d.glob("*.yaml")) + sorted(d.glob("*.yml")):
                    tpl = self._load_file(p)
                    _CACHE[tpl.project_type] = tpl

        self._loaded = True

    def get(self, project_type: str) -> ChapterTemplate | None:
        """Return the cached template for a project type, or None."""
        if not self._loaded:
            self.load_all()
        return _CACHE.get(project_type)

    def load_for_project(self, repo_map: RepoMap) -> ChapterTemplate | None:
        """Load the template matching the repo's classified project type."""
        from .docs_prompts.classify import classify_project

        if not self._loaded:
            self.load_all()

        project_type = classify_project(repo_map)
        return _CACHE.get(project_type)

    def _load_file(self, path: Path) -> ChapterTemplate:
        """Load and validate a single YAML template file."""
        with open(path) as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict):
            msg = f"{path}: template must be a YAML mapping, got {type(raw).__name__}"
            raise TemplateValidationError(msg)

        return self._validate(raw, path)

    def _validate(self, raw: dict, path: Path) -> ChapterTemplate:
        """Validate raw YAML dict and return a ChapterTemplate."""
        # Required top-level fields
        for field_name in ("name", "project_type", "chapters"):
            if field_name not in raw:
                msg = f"{path}: missing required field '{field_name}'"
                raise TemplateValidationError(msg)

        name = str(raw["name"])
        project_type = str(raw["project_type"])

        # project_type validation: known types + custom types are OK
        # (spec says unknown types are accepted for user-defined templates)

        chapters_raw = raw.get("chapters", [])
        if not isinstance(chapters_raw, list):
            msg = f"{path}: 'chapters' must be a list"
            raise TemplateValidationError(msg)

        chapters: list[ChapterDef] = []
        for i, ch_raw in enumerate(chapters_raw):
            if not isinstance(ch_raw, dict):
                msg = f"{path}: chapter #{i} must be a mapping"
                raise TemplateValidationError(msg)

            # Required chapter fields
            for req in ("file", "title", "description"):
                if req not in ch_raw:
                    msg = f"{path}: chapter #{i} missing required field '{req}'"
                    raise TemplateValidationError(msg)

            prompt_key = ch_raw.get("prompt_key")
            prompt_template = ch_raw.get("prompt_template")

            # Must have at least one of prompt_key or prompt_template
            if not prompt_key and not prompt_template:
                msg = (
                    f"{path}: chapter #{i} ('{ch_raw.get('file', '?')}') "
                    f"must have 'prompt_key' or 'prompt_template'"
                )
                raise TemplateValidationError(msg)

            # Validate prompt_key against registry
            if prompt_key and prompt_key not in VALID_PROMPT_KEYS:
                msg = (
                    f"{path}: chapter #{i} has invalid prompt_key '{prompt_key}'. "
                    f"Valid keys: {sorted(VALID_PROMPT_KEYS)}"
                )
                raise TemplateValidationError(msg)

            # Validate condition syntax (dry run)
            condition = ch_raw.get("condition")
            if condition:
                ConditionEvaluator._validate_condition_syntax(condition)

            chapters.append(ChapterDef(
                file=str(ch_raw["file"]),
                title=str(ch_raw["title"]),
                description=str(ch_raw["description"]),
                prompt_key=prompt_key,
                prompt_template=prompt_template,
                condition=condition,
                order=int(ch_raw.get("order", i)),
            ))

        return ChapterTemplate(
            name=name,
            project_type=project_type,
            chapters=tuple(chapters),
        )


# Add condition syntax validation to ConditionEvaluator
def _validate_condition_syntax(condition: str) -> None:
    """Validate condition syntax without evaluating against a RepoMap.

    Raises ConditionError if the expression is malformed or uses
    disallowed functions.
    """
    if not condition or not condition.strip():
        return

    expr = condition.strip()

    # Split on boolean operators and validate each predicate
    parts = re.split(r"\s+(?:and|or)\s+", expr)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if _FUNC_RE.fullmatch(part):
            continue
        if _COMPARE_RE.fullmatch(part):
            continue
        msg = f"Invalid condition syntax: {part!r}"
        raise ConditionError(msg)


ConditionEvaluator._validate_condition_syntax = staticmethod(  # type: ignore[attr-defined]
    _validate_condition_syntax
)


def clear_cache() -> None:
    """Clear the module-level template cache (useful for testing)."""
    _CACHE.clear()
