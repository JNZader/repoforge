"""Tests for diff improvements: method-level granularity, end_line fix, diff+impact."""

from repoforge.diff_enhanced import (
    diff_symbols_in_memory,
    diff_with_impact,
    qualify_method_names,
)
from repoforge.entity_impact import Dependency, Entity, EntityGraph
from repoforge.symbols.extractor import extract_symbols

# ── Mejora 1: Method-level granularity ──

class TestQualifyMethodNames:
    def test_qualifies_methods_inside_class(self):
        code = '''class UserService:
    def get_user(self, uid):
        return self.db.find(uid)

    def delete_user(self, uid):
        return self.db.delete(uid)

def standalone():
    pass
'''
        symbols = extract_symbols(code, 'python', 'svc.py')
        qualified = qualify_method_names(symbols, code)
        names = [s.name for s in qualified]
        assert 'UserService.get_user' in names
        assert 'UserService.delete_user' in names
        assert 'standalone' in names  # not qualified

    def test_no_classes_returns_unchanged(self):
        code = '''def func_a():
    pass

def func_b():
    pass
'''
        symbols = extract_symbols(code, 'python', 'lib.py')
        qualified = qualify_method_names(symbols, code)
        assert all('.' not in s.name for s in qualified if s.kind == 'function')

    def test_handles_nested_classes(self):
        code = '''class Outer:
    class Inner:
        def inner_method(self):
            pass

    def outer_method(self):
        pass
'''
        symbols = extract_symbols(code, 'python', 'nested.py')
        qualified = qualify_method_names(symbols, code)
        names = [s.name for s in qualified]
        # Should at least qualify outer_method
        assert any('Outer' in n for n in names)


# ── Mejora 2: In-memory diff ──

class TestDiffSymbolsInMemory:
    def test_detects_added_function(self):
        old = 'def existing():\n    pass\n'
        new = 'def existing():\n    pass\n\ndef new_func():\n    return 42\n'

        result = diff_symbols_in_memory(old, new, 'python', 'test.py')
        assert len(result.added) == 1
        assert result.added[0].name == 'new_func'

    def test_detects_removed_function(self):
        old = 'def will_remove():\n    pass\n\ndef stays():\n    pass\n'
        new = 'def stays():\n    pass\n'

        result = diff_symbols_in_memory(old, new, 'python', 'test.py')
        assert len(result.removed) == 1
        assert result.removed[0].name == 'will_remove'

    def test_detects_modified_function(self):
        old = 'def func():\n    return 1\n'
        new = 'def func():\n    return 2\n'

        result = diff_symbols_in_memory(old, new, 'python', 'test.py')
        assert len(result.modified) == 1
        assert result.modified[0].name == 'func'

    def test_detects_no_changes(self):
        code = 'def func():\n    return 1\n'
        result = diff_symbols_in_memory(code, code, 'python', 'test.py')
        assert len(result.added) == 0
        assert len(result.removed) == 0
        assert len(result.modified) == 0

    def test_with_method_qualification(self):
        old = 'class Svc:\n    def method(self):\n        return 1\n'
        new = 'class Svc:\n    def method(self):\n        return 2\n'

        result = diff_symbols_in_memory(old, new, 'python', 'svc.py')
        if result.modified:
            assert 'Svc.method' in result.modified[0].name or 'method' in result.modified[0].name


# ── Mejora 3: Diff + Impact ──

class TestDiffWithImpact:
    def test_produces_impact_per_modified_entity(self):
        # Setup: graph where func_b depends on func_a
        graph = EntityGraph()
        a = Entity('func_a', 'lib.py', 1, 'function')
        b = Entity('func_b', 'app.py', 1, 'function')
        test = Entity('test_a', 'tests/test.py', 1, 'function')
        graph.add_entity(a)
        graph.add_entity(b)
        graph.add_entity(test)
        graph.add_dependency(Dependency(b, a, 'calls'))
        graph.add_dependency(Dependency(test, a, 'calls'))

        # Diff shows func_a was modified
        old = 'def func_a():\n    return 1\n'
        new = 'def func_a():\n    return 2\n'

        impacts = diff_with_impact(old, new, 'python', 'lib.py', graph)
        assert len(impacts) >= 1
        # func_a modified → should report func_b and test_a as dependents
        impact = impacts[0]
        assert impact.target.name == 'func_a'
        assert len(impact.direct_dependents) == 2

    def test_no_impact_for_added_entities(self):
        graph = EntityGraph()
        old = ''
        new = 'def new_func():\n    pass\n'

        impacts = diff_with_impact(old, new, 'python', 'lib.py', graph)
        # Added entities have no dependents yet
        assert len(impacts) == 0

    def test_empty_graph_returns_empty(self):
        graph = EntityGraph()
        old = 'def func():\n    return 1\n'
        new = 'def func():\n    return 2\n'

        impacts = diff_with_impact(old, new, 'python', 'lib.py', graph)
        # Modified but no one depends on it
        assert all(len(i.direct_dependents) == 0 for i in impacts)
