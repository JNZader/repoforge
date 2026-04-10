"""Tests for entity_impact — function-level impact analysis."""

import json

from repoforge.entity_impact import (
    Dependency,
    Entity,
    EntityGraph,
    ImpactReport,
    format_impact,
    graph_from_dict,
    graph_to_dict,
)


def _build_graph() -> EntityGraph:
    """Build a realistic dependency graph."""
    g = EntityGraph()

    # Entities
    auth = Entity("authenticateUser", "src/auth.ts", 15, "function")
    validate = Entity("validateToken", "src/auth.ts", 42, "function")
    login = Entity("loginHandler", "src/routes/login.ts", 10, "function")
    dashboard = Entity("loadDashboard", "src/routes/dashboard.ts", 5, "function")
    middleware = Entity("authMiddleware", "src/middleware.ts", 1, "function")
    test_auth = Entity("test_auth", "tests/test_auth.ts", 1, "function")
    test_login = Entity("test_login", "tests/test_login.ts", 1, "function")

    for e in [auth, validate, login, dashboard, middleware, test_auth, test_login]:
        g.add_entity(e)

    # Dependencies
    g.add_dependency(Dependency(login, auth, "calls"))
    g.add_dependency(Dependency(middleware, auth, "calls"))
    g.add_dependency(Dependency(auth, validate, "calls"))
    g.add_dependency(Dependency(dashboard, middleware, "calls"))
    g.add_dependency(Dependency(test_auth, auth, "calls"))
    g.add_dependency(Dependency(test_login, login, "calls"))

    return g


class TestEntityGraph:
    def test_add_and_find(self):
        g = EntityGraph()
        e = Entity("myFunc", "src/lib.ts", 10)
        g.add_entity(e)
        assert g.get_entity("src/lib.ts", "myFunc") is not None

    def test_find_by_name(self):
        g = _build_graph()
        found = g.find_entity("authenticateUser")
        assert len(found) == 1
        assert found[0].file == "src/auth.ts"

    def test_get_dependents(self):
        g = _build_graph()
        auth = g.get_entity("src/auth.ts", "authenticateUser")
        deps = g.get_dependents(auth)
        names = [d.name for d in deps]
        assert "loginHandler" in names
        assert "authMiddleware" in names
        assert "test_auth" in names

    def test_get_dependencies_of(self):
        g = _build_graph()
        login = g.get_entity("src/routes/login.ts", "loginHandler")
        deps = g.get_dependencies_of(login)
        assert any(d.name == "authenticateUser" for d in deps)


class TestImpactAnalysis:
    def test_direct_impact(self):
        g = _build_graph()
        auth = g.get_entity("src/auth.ts", "authenticateUser")
        report = g.analyze_impact(auth)
        assert len(report.direct_dependents) == 3  # login, middleware, test_auth

    def test_transitive_impact(self):
        g = _build_graph()
        validate = g.get_entity("src/auth.ts", "validateToken")
        report = g.analyze_impact(validate, max_depth=3)
        # validateToken → authenticateUser → login, middleware, test_auth → dashboard, test_login
        assert len(report.transitive_dependents) > 0

    def test_affected_tests(self):
        g = _build_graph()
        auth = g.get_entity("src/auth.ts", "authenticateUser")
        report = g.analyze_impact(auth)
        assert any("test" in t for t in report.affected_tests)

    def test_risk_level_safe(self):
        g = EntityGraph()
        isolated = Entity("isolated", "src/orphan.ts", 1)
        g.add_entity(isolated)
        report = g.analyze_impact(isolated)
        assert report.risk_level == "safe"

    def test_risk_level_high(self):
        g = _build_graph()
        auth = g.get_entity("src/auth.ts", "authenticateUser")
        report = g.analyze_impact(auth, max_depth=3)
        assert report.risk_level in ("medium", "high")

    def test_max_depth_limits_traversal(self):
        g = _build_graph()
        validate = g.get_entity("src/auth.ts", "validateToken")
        shallow = g.analyze_impact(validate, max_depth=1)
        deep = g.analyze_impact(validate, max_depth=3)
        assert len(deep.transitive_dependents) >= len(shallow.transitive_dependents)


class TestFormatImpact:
    def test_produces_markdown(self):
        g = _build_graph()
        auth = g.get_entity("src/auth.ts", "authenticateUser")
        report = g.analyze_impact(auth)
        text = format_impact(report)
        assert "## Impact Analysis" in text
        assert "authenticateUser" in text
        assert "Direct dependents" in text

    def test_safe_entity(self):
        g = EntityGraph()
        e = Entity("lonely", "src/lonely.ts", 1)
        g.add_entity(e)
        report = g.analyze_impact(e)
        text = format_impact(report)
        assert "safe to modify" in text


class TestSerialization:
    def test_roundtrip(self):
        g = _build_graph()
        data = graph_to_dict(g)
        restored = graph_from_dict(data)
        assert len(restored.entities) == len(g.entities)
        assert len(restored.dependencies) == len(g.dependencies)

    def test_json_serializable(self):
        g = _build_graph()
        json_str = json.dumps(graph_to_dict(g))
        assert json_str
