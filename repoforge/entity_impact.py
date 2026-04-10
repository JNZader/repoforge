"""Entity-granularity impact analysis — "what breaks if I change this function?"

Unlike file-level blast radius, this operates at the symbol level:
functions, classes, methods. Given a target entity, it finds all
direct callers, dependents, and affected tests.

Algorithm:
  1. Build a symbol→symbol dependency graph from AST imports and calls
  2. For a target symbol, find all direct dependents (callers)
  3. Find transitive dependents up to a configurable depth
  4. Identify affected test files (files matching *test* that depend)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Entity:
    """A code entity (function, class, method) with its location."""
    name: str
    file: str
    line: int = 0
    kind: str = "function"  # function, class, method, variable


@dataclass(frozen=True)
class Dependency:
    """A dependency between two entities."""
    source: Entity  # the caller/importer
    target: Entity  # the callee/imported
    kind: str = "calls"  # calls, imports, extends, uses


@dataclass
class ImpactReport:
    """Impact analysis result for a target entity."""
    target: Entity
    direct_dependents: list[Entity] = field(default_factory=list)
    transitive_dependents: list[Entity] = field(default_factory=list)
    affected_tests: list[str] = field(default_factory=list)
    depth: int = 0

    @property
    def total_affected(self) -> int:
        return len(set(
            [e.file for e in self.direct_dependents] +
            [e.file for e in self.transitive_dependents]
        ))

    @property
    def risk_level(self) -> str:
        n = self.total_affected
        if n == 0:
            return "safe"
        if n <= 2:
            return "low"
        if n <= 5:
            return "medium"
        return "high"


@dataclass
class EntityGraph:
    """A graph of entity dependencies for impact analysis."""
    entities: dict[str, Entity] = field(default_factory=dict)
    dependencies: list[Dependency] = field(default_factory=list)

    def add_entity(self, entity: Entity) -> None:
        key = f"{entity.file}:{entity.name}"
        self.entities[key] = entity

    def add_dependency(self, dep: Dependency) -> None:
        self.dependencies.append(dep)

    def get_entity(self, file: str, name: str) -> Entity | None:
        return self.entities.get(f"{file}:{name}")

    def find_entity(self, name: str) -> list[Entity]:
        """Find all entities matching a name (may be in multiple files)."""
        return [e for e in self.entities.values() if e.name == name]

    def get_dependents(self, target: Entity) -> list[Entity]:
        """Find all entities that directly depend on the target."""
        target_key = f"{target.file}:{target.name}"
        result: list[Entity] = []
        for dep in self.dependencies:
            dep_target_key = f"{dep.target.file}:{dep.target.name}"
            if dep_target_key == target_key:
                result.append(dep.source)
        return result

    def get_dependencies_of(self, source: Entity) -> list[Entity]:
        """Find all entities that the source depends on."""
        source_key = f"{source.file}:{source.name}"
        result: list[Entity] = []
        for dep in self.dependencies:
            dep_source_key = f"{dep.source.file}:{dep.source.name}"
            if dep_source_key == source_key:
                result.append(dep.target)
        return result

    def analyze_impact(
        self, target: Entity, *, max_depth: int = 3,
    ) -> ImpactReport:
        """Analyze the impact of changing a target entity."""
        direct = self.get_dependents(target)

        # BFS for transitive dependents
        visited: set[str] = {f"{target.file}:{target.name}"}
        for d in direct:
            visited.add(f"{d.file}:{d.name}")

        transitive: list[Entity] = []
        frontier = list(direct)
        depth = 0

        while frontier and depth < max_depth:
            next_frontier: list[Entity] = []
            for entity in frontier:
                for dep in self.get_dependents(entity):
                    key = f"{dep.file}:{dep.name}"
                    if key not in visited:
                        visited.add(key)
                        transitive.append(dep)
                        next_frontier.append(dep)
            frontier = next_frontier
            depth += 1

        # Find affected test files
        all_affected_files = set(
            e.file for e in direct + transitive
        )
        affected_tests = sorted(
            f for f in all_affected_files
            if "test" in f.lower() or "spec" in f.lower()
        )

        return ImpactReport(
            target=target,
            direct_dependents=direct,
            transitive_dependents=transitive,
            affected_tests=affected_tests,
            depth=depth,
        )


def format_impact(report: ImpactReport) -> str:
    """Format an impact report as readable text."""
    lines: list[str] = []
    lines.append(f"## Impact Analysis: {report.target.name}")
    lines.append(f"**File**: `{report.target.file}:{report.target.line}`")
    lines.append(f"**Risk**: {report.risk_level} ({report.total_affected} files affected)")
    lines.append("")

    if report.direct_dependents:
        lines.append(f"### Direct dependents ({len(report.direct_dependents)})")
        for e in report.direct_dependents:
            lines.append(f"- `{e.file}:{e.name}` ({e.kind})")
        lines.append("")

    if report.transitive_dependents:
        lines.append(f"### Transitive dependents ({len(report.transitive_dependents)})")
        for e in report.transitive_dependents:
            lines.append(f"- `{e.file}:{e.name}` ({e.kind})")
        lines.append("")

    if report.affected_tests:
        lines.append(f"### Affected tests ({len(report.affected_tests)})")
        for t in report.affected_tests:
            lines.append(f"- `{t}`")
        lines.append("")

    if not report.direct_dependents and not report.transitive_dependents:
        lines.append("No dependents found — safe to modify.\n")

    return "\n".join(lines)


def graph_to_dict(graph: EntityGraph) -> dict[str, Any]:
    return {
        "entities": [
            {"name": e.name, "file": e.file, "line": e.line, "kind": e.kind}
            for e in graph.entities.values()
        ],
        "dependencies": [
            {
                "source": {"name": d.source.name, "file": d.source.file},
                "target": {"name": d.target.name, "file": d.target.file},
                "kind": d.kind,
            }
            for d in graph.dependencies
        ],
    }


def graph_from_dict(data: dict[str, Any]) -> EntityGraph:
    graph = EntityGraph()
    for e in data.get("entities", []):
        graph.add_entity(Entity(**e))
    for d in data.get("dependencies", []):
        graph.add_dependency(Dependency(
            source=Entity(name=d["source"]["name"], file=d["source"]["file"]),
            target=Entity(name=d["target"]["name"], file=d["target"]["file"]),
            kind=d.get("kind", "calls"),
        ))
    return graph
