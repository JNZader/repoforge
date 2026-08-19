"""Direct regression tests for the C# tree-sitter extractor."""

from repoforge.intelligence.lang_csharp import CSharpASTExtractor


def test_csharp_parser_acquisition_parses_an_ordinary_class():
    extractor = CSharpASTExtractor()

    assert extractor._parser is not None
    symbols = extractor.extract_symbols(
        "public class Plain { public int Id { get; set; } }",
        "Plain.cs",
    )

    assert [(symbol.name, symbol.kind) for symbol in symbols] == [("Plain", "class")]


def test_ordinary_class_is_not_a_schema():
    schemas = CSharpASTExtractor().extract_schemas(
        "public class Plain { public int Id { get; set; } }",
        "Plain.cs",
    )

    assert schemas == []


def test_table_attribute_marks_a_schema_with_metadata():
    schemas = CSharpASTExtractor().extract_schemas(
        '[Table("users")]\npublic class User { public int Id { get; set; } }',
        "User.cs",
    )

    assert len(schemas) == 1
    schema = schemas[0]
    assert (schema.name, schema.kind, schema.signature) == ("User", "schema", "class User")
    assert schema.decorators == ['[Table("users")]']
    assert schema.fields == ["public int Id { get; set; }"]
    assert (schema.file, schema.line) == ("User.cs", 1)


def test_dbcontext_base_marks_a_schema():
    schemas = CSharpASTExtractor().extract_schemas(
        "public class AppDbContext : DbContext { }",
        "AppDbContext.cs",
    )

    assert [(schema.name, schema.kind, schema.file) for schema in schemas] == [
        ("AppDbContext", "schema", "AppDbContext.cs"),
    ]


def test_incidental_dbcontext_body_text_does_not_mark_a_schema():
    schemas = CSharpASTExtractor().extract_schemas(
        'public class Plain { public string Description = "DbContext helper"; }',
        "Plain.cs",
    )

    assert schemas == []
