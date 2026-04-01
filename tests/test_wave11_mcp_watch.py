"""Tests for Wave 11: MCP tool definitions + watch mode."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from repoforge.mcp_tools import (
    get_mcp_tool_definitions,
    get_mcp_resource_definitions,
)
from repoforge.watch import FileWatcher, WatchEvent, _format_events, _make_watch_logger


# ── MCP tool definitions ─────────────────────────────────────────────────


class TestMCPToolDefinitions:

    def test_returns_list(self):
        tools = get_mcp_tool_definitions()
        assert isinstance(tools, list)
        assert len(tools) >= 4  # generate, score, graph, scan

    def test_each_tool_has_required_fields(self):
        tools = get_mcp_tool_definitions()
        for tool in tools:
            assert "name" in tool, f"Tool missing name: {tool}"
            assert "description" in tool, f"Tool missing description: {tool}"
            assert "inputSchema" in tool, f"Tool missing inputSchema: {tool}"

    def test_tool_names(self):
        tools = get_mcp_tool_definitions()
        names = [t["name"] for t in tools]
        assert "repoforge_generate_docs" in names
        assert "repoforge_score" in names
        assert "repoforge_graph" in names

    def test_input_schema_is_valid_json_schema(self):
        tools = get_mcp_tool_definitions()
        for tool in tools:
            schema = tool["inputSchema"]
            assert schema["type"] == "object"
            assert "properties" in schema

    def test_generate_docs_has_key_params(self):
        tools = get_mcp_tool_definitions()
        gen = next(t for t in tools if t["name"] == "repoforge_generate_docs")
        props = gen["inputSchema"]["properties"]
        assert "working_dir" in props
        assert "language" in props
        assert "persona" in props

    def test_serializable_to_json(self):
        tools = get_mcp_tool_definitions()
        serialized = json.dumps(tools)
        assert isinstance(serialized, str)
        parsed = json.loads(serialized)
        assert len(parsed) == len(tools)


class TestMCPResourceDefinitions:

    def test_returns_list(self):
        resources = get_mcp_resource_definitions()
        assert isinstance(resources, list)

    def test_each_resource_has_uri_and_name(self):
        resources = get_mcp_resource_definitions()
        for r in resources:
            assert "uri" in r
            assert "name" in r

    def test_docs_resource_exists(self):
        resources = get_mcp_resource_definitions()
        uris = [r["uri"] for r in resources]
        assert any("docs" in u for u in uris)


# ── FileWatcher ──────────────────────────────────────────────────────────


class TestFileWatcher:

    def test_detects_file_change(self, tmp_path):
        (tmp_path / "app.py").write_text("v1\n")
        watcher = FileWatcher(tmp_path)
        snapshot1 = watcher.snapshot()

        (tmp_path / "app.py").write_text("v2\n")
        snapshot2 = watcher.snapshot()

        events = watcher.diff(snapshot1, snapshot2)
        assert len(events) >= 1
        assert any(e.path == "app.py" and e.event_type == "modified" for e in events)

    def test_detects_new_file(self, tmp_path):
        (tmp_path / "app.py").write_text("v1\n")
        watcher = FileWatcher(tmp_path)
        snapshot1 = watcher.snapshot()

        (tmp_path / "new.py").write_text("new\n")
        snapshot2 = watcher.snapshot()

        events = watcher.diff(snapshot1, snapshot2)
        assert any(e.path == "new.py" and e.event_type == "added" for e in events)

    def test_detects_deleted_file(self, tmp_path):
        (tmp_path / "app.py").write_text("v1\n")
        (tmp_path / "old.py").write_text("old\n")
        watcher = FileWatcher(tmp_path)
        snapshot1 = watcher.snapshot()

        (tmp_path / "old.py").unlink()
        snapshot2 = watcher.snapshot()

        events = watcher.diff(snapshot1, snapshot2)
        assert any(e.path == "old.py" and e.event_type == "removed" for e in events)

    def test_no_changes_returns_empty(self, tmp_path):
        (tmp_path / "app.py").write_text("stable\n")
        watcher = FileWatcher(tmp_path)
        snapshot1 = watcher.snapshot()
        snapshot2 = watcher.snapshot()
        events = watcher.diff(snapshot1, snapshot2)
        assert events == []

    def test_respects_extensions_filter(self, tmp_path):
        (tmp_path / "app.py").write_text("v1\n")
        (tmp_path / "readme.md").write_text("# Hi\n")
        watcher = FileWatcher(tmp_path, extensions={".py"})
        snapshot1 = watcher.snapshot()

        (tmp_path / "app.py").write_text("v2\n")
        (tmp_path / "readme.md").write_text("# Updated\n")
        snapshot2 = watcher.snapshot()

        events = watcher.diff(snapshot1, snapshot2)
        paths = [e.path for e in events]
        assert "app.py" in paths
        assert "readme.md" not in paths

    def test_watch_event_fields(self):
        e = WatchEvent(path="app.py", event_type="modified")
        assert e.path == "app.py"
        assert e.event_type == "modified"


# ── Watch mode helpers ──────────────────────────────────────────────────


class TestFormatEvents:

    def test_formats_added_modified_removed(self):
        events = [
            WatchEvent(path="new.py", event_type="added"),
            WatchEvent(path="old.py", event_type="modified"),
            WatchEvent(path="gone.py", event_type="removed"),
        ]
        output = _format_events(events)
        assert "+ new.py" in output
        assert "~ old.py" in output
        assert "- gone.py" in output

    def test_empty_events(self):
        assert _format_events([]) == ""


class TestMakeWatchLogger:

    def test_verbose_prints(self, capsys):
        log = _make_watch_logger(verbose=True)
        log("hello watch")
        captured = capsys.readouterr()
        assert "hello watch" in captured.out

    def test_quiet_suppresses(self, capsys):
        log = _make_watch_logger(verbose=False)
        log("should not appear")
        captured = capsys.readouterr()
        assert captured.out == ""


class TestWatchDocsLoop:
    """Test watch_docs loop behaviour using mocks."""

    @patch("repoforge.docs_generator.generate_docs")
    @patch("repoforge.watch.time.sleep")
    def test_detects_change_and_regenerates(self, mock_sleep, mock_gen, tmp_path):
        """Simulate: initial gen → one poll with changes → KeyboardInterrupt."""
        (tmp_path / "app.py").write_text("v1\n")

        call_count = 0
        def sleep_side_effect(_interval):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Simulate a file change during first sleep
                (tmp_path / "app.py").write_text("v2\n")
            elif call_count >= 2:
                raise KeyboardInterrupt

        mock_sleep.side_effect = sleep_side_effect
        mock_gen.return_value = {
            "chapters_generated": ["docs/01-overview.md"],
            "skipped": [],
        }

        with pytest.raises(SystemExit):
            from repoforge.watch import watch_docs
            watch_docs(
                working_dir=str(tmp_path),
                output_dir="docs",
                interval=0.1,
                verbose=False,
            )

        # Initial generation + at least one incremental regeneration
        assert mock_gen.call_count >= 2
        # All calls should have incremental=True
        for c in mock_gen.call_args_list:
            assert c.kwargs.get("incremental") is True or c[1].get("incremental") is True

    @patch("repoforge.docs_generator.generate_docs")
    @patch("repoforge.watch.time.sleep")
    def test_no_change_skips_regeneration(self, mock_sleep, mock_gen, tmp_path):
        """If no files change, generate_docs should only be called once (initial)."""
        (tmp_path / "app.py").write_text("stable\n")

        call_count = 0
        def sleep_side_effect(_interval):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise KeyboardInterrupt

        mock_sleep.side_effect = sleep_side_effect
        mock_gen.return_value = {"chapters_generated": [], "skipped": []}

        with pytest.raises(SystemExit):
            from repoforge.watch import watch_docs
            watch_docs(
                working_dir=str(tmp_path),
                output_dir="docs",
                interval=0.1,
                verbose=False,
            )

        # Only the initial generation call
        assert mock_gen.call_count == 1

    @patch("repoforge.docs_generator.generate_docs")
    @patch("repoforge.watch.time.sleep")
    def test_regeneration_error_does_not_crash(self, mock_sleep, mock_gen, tmp_path):
        """If generate_docs raises, the loop should continue."""
        (tmp_path / "app.py").write_text("v1\n")

        call_count = 0
        def sleep_side_effect(_interval):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                (tmp_path / "app.py").write_text("v2\n")
            elif call_count >= 2:
                raise KeyboardInterrupt

        mock_sleep.side_effect = sleep_side_effect
        # Initial succeeds, second call raises
        mock_gen.side_effect = [
            {"chapters_generated": [], "skipped": []},
            RuntimeError("LLM unavailable"),
        ]

        with pytest.raises(SystemExit):
            from repoforge.watch import watch_docs
            watch_docs(
                working_dir=str(tmp_path),
                output_dir="docs",
                interval=0.1,
                verbose=False,
            )

        assert mock_gen.call_count == 2
