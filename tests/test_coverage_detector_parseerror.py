"""S6 regression: resilient handling of malformed coverage input.

`auto_detect_and_parse` MUST catch `xml.etree.ElementTree.ParseError` (a
`SyntaxError` subclass) from malformed coverage XML, log/skip that report,
continue processing other reports, and preserve valid-report parsing/results.

Strict-TDD note: before the production fix these tests are RED — the
`ParseError` escapes `auto_detect_and_parse`'s `except (OSError, ValueError,
KeyError)` tuple (it is NOT a subclass of any of those) and aborts the run.
"""

import xml.etree.ElementTree as ET

from repoforge.coverage.detector import auto_detect_and_parse

MINIMAL_COBERTURA = """\
<?xml version="1.0" ?>
<coverage line-rate="0.8">
  <packages>
    <package name="app">
      <classes>
        <class name="main.py" filename="app/main.py" line-rate="0.8">
          <lines><line number="1" hits="1"/><line number="2" hits="0"/></lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>
"""

MINIMAL_LCOV = """\
TN:
SF:src/index.ts
LF:10
LH:8
end_of_record
"""


class TestCoverageMalformedInputHandling:

    def test_malformed_xml_is_skipped_not_crashed(self, tmp_path):
        (tmp_path / "coverage.xml").write_text("<coverage><not valid xml")
        reports = auto_detect_and_parse(tmp_path)
        # Malformed XML must be skipped, not abort the whole run.
        assert len(reports) == 0

    def test_mixed_valid_and_malformed_retains_valid(self, tmp_path):
        (tmp_path / "coverage.xml").write_text("<coverage><not valid xml")
        (tmp_path / "cobertura.xml").write_text(MINIMAL_COBERTURA)
        reports = auto_detect_and_parse(tmp_path)
        # Valid report must be parsed and returned; malformed skipped.
        assert len(reports) == 1
        assert reports[0].source_format == "cobertura"
        assert len(reports[0].files) == 1

    def test_mixed_valid_and_malformed_no_parseerror_propagates(self, tmp_path):
        (tmp_path / "coverage.xml").write_text("<coverage><not valid xml")
        (tmp_path / "lcov.info").write_text(MINIMAL_LCOV)
        # The ParseError must NOT escape auto_detect_and_parse.
        try:
            reports = auto_detect_and_parse(tmp_path)
        except ET.ParseError as exc:
            raise AssertionError(
                "xml.etree.ElementTree.ParseError leaked out of auto_detect_and_parse"
            ) from exc
        assert len(reports) == 1
        assert reports[0].source_format == "lcov"
