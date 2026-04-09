"""Tests for Ruby AST extractor — tree-sitter based."""

import pytest

from repoforge.intelligence.lang_ruby import RubyASTExtractor


@pytest.fixture
def extractor():
    return RubyASTExtractor()


class TestRubySymbols:
    """Ruby symbol extraction."""

    def test_method(self, extractor):
        code = "def greet(name)\n  puts name\nend"
        symbols = extractor.extract_symbols(code, "main.rb")

        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "greet"
        assert "def greet" in funcs[0].signature

    def test_class_with_methods(self, extractor):
        code = """class UserService
  def find_by_id(id)
    User.find(id)
  end

  def self.create(attrs)
    new(attrs)
  end
end"""
        symbols = extractor.extract_symbols(code, "service.rb")

        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "UserService"

        methods = [s for s in symbols if s.kind == "method"]
        assert len(methods) >= 1
        method_names = {m.name for m in methods}
        assert "find_by_id" in method_names

    def test_class_with_superclass(self, extractor):
        code = "class Admin < User\nend"
        symbols = extractor.extract_symbols(code, "admin.rb")

        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "Admin"
        assert "< User" in classes[0].signature

    def test_module(self, extractor):
        code = "module Authenticatable\n  def authenticate(token)\n    true\n  end\nend"
        symbols = extractor.extract_symbols(code, "auth.rb")

        mods = [s for s in symbols if s.name == "Authenticatable"]
        assert len(mods) == 1
        assert "module Authenticatable" in mods[0].signature

    def test_empty_file(self, extractor):
        assert extractor.extract_symbols("", "empty.rb") == []

    def test_endpoints_empty(self, extractor):
        code = "def hello\n  'world'\nend"
        assert extractor.extract_endpoints(code, "main.rb") == []

    def test_schemas_empty(self, extractor):
        code = "class Plain\nend"
        assert extractor.extract_schemas(code, "plain.rb") == []


class TestRubySchemas:
    """Ruby schema extraction — ActiveRecord."""

    def test_active_record_model(self, extractor):
        code = "class User < ApplicationRecord\n  validates :name, presence: true\nend"
        schemas = extractor.extract_schemas(code, "user.rb")

        assert len(schemas) == 1
        assert schemas[0].name == "User"
        assert schemas[0].kind == "schema"
