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


def test_custom_return_type_does_not_replace_method_name():
    symbols = CSharpASTExtractor().extract_symbols(
        "public class UsersController { public User GetUser(int id) => new User(); }",
        "UsersController.cs",
    )

    method = next(symbol for symbol in symbols if symbol.kind == "method")
    assert (method.name, method.signature, method.return_type) == (
        "GetUser",
        "User GetUser(int id)",
        "User",
    )


def test_builtin_return_type_and_constructor_names_remain_unchanged():
    symbols = CSharpASTExtractor().extract_symbols(
        """
        public class UsersController {
            public int GetCount() => 1;
            public UsersController() { }
        }
        """,
        "UsersController.cs",
    )

    methods = [(symbol.name, symbol.signature) for symbol in symbols if symbol.kind == "method"]
    assert methods == [
        ("GetCount", "int GetCount()"),
        ("UsersController", "UsersController()"),
    ]


def test_route_attributes_accept_zero_one_and_trailing_named_arguments():
    endpoints = CSharpASTExtractor().extract_endpoints(
        """
        public class UsersController {
            [HttpGet]
            public User List() => new User();

            [HttpGet("users")]
            public User ListUsers() => new User();

            [HttpGet("users/{id}", Name = "GetUser")]
            public User GetUser(int id) => new User();
        }
        """,
        "UsersController.cs",
    )

    assert [endpoint.value for endpoint in endpoints] == [
        "GET",
        "GET users",
        "GET users/{id}",
    ]


def test_malformed_route_attribute_is_not_extracted():
    endpoints = CSharpASTExtractor().extract_endpoints(
        """
        public class UsersController {
            [HttpGet("users/{id}", Name = )]
            public User GetUser(int id) => new User();
        }
        """,
        "UsersController.cs",
    )

    assert endpoints == []
