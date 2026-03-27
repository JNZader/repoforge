"""Tests for Java AST extractor — tree-sitter based."""

import pytest

from repoforge.intelligence.lang_java import JavaASTExtractor


@pytest.fixture
def extractor():
    return JavaASTExtractor()


class TestJavaSymbols:
    """Java symbol extraction."""

    def test_class(self, extractor):
        code = '''public class User {
    private String name;
    private int age;
}'''
        symbols = extractor.extract_symbols(code, "User.java")

        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "User"
        assert len(classes[0].fields) == 2

    def test_interface(self, extractor):
        code = '''public interface UserRepository {
    User findById(Long id);
    List<User> findAll();
}'''
        symbols = extractor.extract_symbols(code, "UserRepository.java")

        ifaces = [s for s in symbols if s.kind == "interface"]
        assert len(ifaces) == 1
        assert ifaces[0].name == "UserRepository"

    def test_enum(self, extractor):
        code = 'public enum Status { ACTIVE, INACTIVE }'
        symbols = extractor.extract_symbols(code, "Status.java")

        types = [s for s in symbols if s.kind == "type"]
        assert len(types) == 1
        assert types[0].name == "Status"

    def test_record(self, extractor):
        code = 'public record UserDTO(String name, int age) {}'
        symbols = extractor.extract_symbols(code, "UserDTO.java")

        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "UserDTO"
        assert len(classes[0].params) == 2

    def test_methods(self, extractor):
        code = '''public class Service {
    public User getUser(Long id) {
        return null;
    }
    public void deleteUser(Long id) {}
}'''
        symbols = extractor.extract_symbols(code, "Service.java")

        methods = [s for s in symbols if s.kind == "method"]
        assert len(methods) == 2
        names = {m.name for m in methods}
        assert "getUser" in names
        assert "deleteUser" in names

    def test_annotated_class(self, extractor):
        code = '''@RestController
@RequestMapping("/api")
public class ApiController {
    @GetMapping("/health")
    public String health() { return "ok"; }
}'''
        symbols = extractor.extract_symbols(code, "ApiController.java")

        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 1
        assert len(classes[0].decorators) >= 1


class TestJavaEndpoints:
    """Java endpoint extraction."""

    def test_spring_get_mapping(self, extractor):
        code = '''public class Controller {
    @GetMapping("/users/{id}")
    public User getUser(@PathVariable Long id) {
        return null;
    }
}'''
        endpoints = extractor.extract_endpoints(code, "Controller.java")
        assert len(endpoints) == 1
        assert "GET" in endpoints[0].value
        assert "/users/{id}" in endpoints[0].value

    def test_spring_post_mapping(self, extractor):
        code = '''public class Controller {
    @PostMapping("/users")
    public User createUser(@RequestBody User user) {
        return user;
    }
}'''
        endpoints = extractor.extract_endpoints(code, "Controller.java")
        assert len(endpoints) == 1
        assert "POST" in endpoints[0].value

    def test_no_endpoints(self, extractor):
        code = '''public class Service {
    public void process() {}
}'''
        endpoints = extractor.extract_endpoints(code, "Service.java")
        assert len(endpoints) == 0


class TestJavaSchemas:
    """Java JPA schema extraction."""

    def test_entity_class(self, extractor):
        code = '''@Entity
@Table(name = "users")
public class User {
    @Id
    private Long id;
    private String name;
}'''
        schemas = extractor.extract_schemas(code, "User.java")
        assert len(schemas) == 1
        assert schemas[0].name == "User"
        assert schemas[0].kind == "schema"
        assert len(schemas[0].fields) >= 1

    def test_non_entity_excluded(self, extractor):
        code = '''public class RegularClass {
    private int value;
}'''
        schemas = extractor.extract_schemas(code, "Regular.java")
        assert len(schemas) == 0
