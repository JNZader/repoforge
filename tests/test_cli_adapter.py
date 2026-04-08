"""Tests for the CLI LLM adapter (cli_adapter.py) and build_llm CLI routing."""

import re
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from repoforge.cli_adapter import (
    CLI_REGISTRY,
    CliLLMAdapter,
    CliToolConfig,
    sanitize_output,
)
from repoforge.llm import LLMProvider, build_llm

# ---------------------------------------------------------------------------
# 4.1 — CliToolConfig construction and registry lookup
# ---------------------------------------------------------------------------


class TestCliToolConfig:
    def test_config_is_immutable(self):
        cfg = CliToolConfig(binary="test", prompt_mode="arg")
        with pytest.raises(AttributeError):
            cfg.binary = "other"  # type: ignore[misc]

    def test_default_fields(self):
        cfg = CliToolConfig(binary="test", prompt_mode="arg")
        assert cfg.cmd_template == []
        assert cfg.system_flag is None
        assert cfg.stream_args is None
        assert cfg.supports_stream is False
        assert cfg.output_patterns == []
        assert cfg.timeout == 120

    def test_registry_has_expected_tools(self):
        assert "claude" in CLI_REGISTRY
        assert "codex" in CLI_REGISTRY
        assert "opencode" in CLI_REGISTRY

    def test_registry_lookup_returns_config(self):
        cfg = CLI_REGISTRY["claude"]
        assert isinstance(cfg, CliToolConfig)
        assert cfg.binary == "claude"
        assert cfg.supports_stream is True

    def test_codex_has_no_system_flag(self):
        assert CLI_REGISTRY["codex"].system_flag is None

    def test_opencode_has_no_system_flag(self):
        assert CLI_REGISTRY["opencode"].system_flag is None


# ---------------------------------------------------------------------------
# 4.2 — sanitize_output
# ---------------------------------------------------------------------------


class TestSanitizeOutput:
    def test_strips_ansi_codes(self):
        text = "\x1b[31mhello\x1b[0m world"
        assert sanitize_output(text) == "hello world"

    def test_strips_complex_ansi(self):
        text = "\x1b[1;32;40mcolored\x1b[0m"
        assert sanitize_output(text) == "colored"

    def test_strips_tool_specific_patterns(self):
        patterns = [re.compile(r"^BANNER:.*")]
        text = "BANNER: some noise\nactual content"
        assert sanitize_output(text, patterns) == "actual content"

    def test_strips_whitespace(self):
        assert sanitize_output("  hello  \n\n") == "hello"

    def test_empty_string(self):
        assert sanitize_output("") == ""

    def test_no_patterns_no_crash(self):
        assert sanitize_output("clean text", None) == "clean text"

    def test_codex_patterns(self):
        patterns = CLI_REGISTRY["codex"].output_patterns
        text = "\x1b[1;33msome output"
        result = sanitize_output(text, patterns)
        # Should strip both ANSI and codex-specific patterns
        assert "\x1b[" not in result


# ---------------------------------------------------------------------------
# 4.3 — _build_command for each tool
# ---------------------------------------------------------------------------


class TestBuildCommand:
    @patch("shutil.which", return_value="/usr/bin/claude")
    def test_claude_with_system(self, _mock_which):
        adapter = CliLLMAdapter(CLI_REGISTRY["claude"])
        cmd = adapter._build_command("my prompt", system="be helpful")
        assert cmd[0] == "claude"
        assert "--system-prompt" in cmd
        idx = cmd.index("--system-prompt")
        assert cmd[idx + 1] == "be helpful"
        assert cmd[-1] == "my prompt"

    @patch("shutil.which", return_value="/usr/bin/claude")
    def test_claude_without_system(self, _mock_which):
        adapter = CliLLMAdapter(CLI_REGISTRY["claude"])
        cmd = adapter._build_command("my prompt")
        assert "--system-prompt" not in cmd
        assert cmd[-1] == "my prompt"

    @patch("shutil.which", return_value="/usr/bin/codex")
    def test_codex_no_system_flag(self, _mock_which):
        adapter = CliLLMAdapter(CLI_REGISTRY["codex"])
        cmd = adapter._build_command("my prompt", system="be helpful")
        # codex has no system_flag, so system is prepended to prompt
        assert "--system-prompt" not in cmd
        assert "System: be helpful" in cmd[-1]

    @patch("shutil.which", return_value="/usr/bin/opencode")
    def test_opencode_command_structure(self, _mock_which):
        adapter = CliLLMAdapter(CLI_REGISTRY["opencode"])
        cmd = adapter._build_command("explain monads")
        assert cmd[0] == "opencode"
        assert "run" in cmd
        assert cmd[-1] == "explain monads"

    @patch("shutil.which", return_value="/usr/bin/claude")
    def test_claude_includes_template_flags(self, _mock_which):
        adapter = CliLLMAdapter(CLI_REGISTRY["claude"])
        cmd = adapter._build_command("test")
        assert "-p" in cmd
        assert "--output-format" in cmd
        assert "text" in cmd
        assert "--no-input" in cmd


# ---------------------------------------------------------------------------
# 4.4 — complete() with mocked subprocess.run
# ---------------------------------------------------------------------------


class TestComplete:
    @patch("shutil.which", return_value="/usr/bin/claude")
    @patch("subprocess.run")
    def test_success(self, mock_run, _mock_which):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="The answer is 42\n",
            stderr="",
        )
        adapter = CliLLMAdapter(CLI_REGISTRY["claude"])
        result = adapter.complete("What is the answer?")
        assert result == "The answer is 42"
        mock_run.assert_called_once()

    @patch("shutil.which", return_value="/usr/bin/claude")
    @patch("subprocess.run")
    def test_failure_raises_runtime_error(self, mock_run, _mock_which):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="API error: rate limited",
        )
        adapter = CliLLMAdapter(CLI_REGISTRY["claude"])
        with pytest.raises(RuntimeError, match="failed"):
            adapter.complete("test")

    @patch("shutil.which", return_value="/usr/bin/claude")
    @patch("subprocess.run")
    def test_timeout_raises_runtime_error(self, mock_run, _mock_which):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["claude"], timeout=120)
        adapter = CliLLMAdapter(CLI_REGISTRY["claude"])
        with pytest.raises(RuntimeError, match="timed out"):
            adapter.complete("test")

    @patch("shutil.which", return_value="/usr/bin/claude")
    @patch("subprocess.run")
    def test_file_not_found_raises_runtime_error(self, mock_run, _mock_which):
        mock_run.side_effect = FileNotFoundError()
        adapter = CliLLMAdapter(CLI_REGISTRY["claude"])
        with pytest.raises(RuntimeError, match="not found"):
            adapter.complete("test")

    @patch("shutil.which", return_value="/usr/bin/claude")
    @patch("subprocess.run")
    def test_sanitizes_output(self, mock_run, _mock_which):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="\x1b[32mgreen text\x1b[0m\n",
            stderr="",
        )
        adapter = CliLLMAdapter(CLI_REGISTRY["claude"])
        result = adapter.complete("test")
        assert "\x1b[" not in result
        assert result == "green text"


# ---------------------------------------------------------------------------
# 4.5 — stream() with mocked Popen
# ---------------------------------------------------------------------------


class TestStream:
    @patch("shutil.which", return_value="/usr/bin/codex")
    @patch("subprocess.run")
    def test_non_streaming_tool_falls_back_to_complete(self, mock_run, _mock_which):
        """codex doesn't support streaming — stream() should call complete()."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="fallback response",
            stderr="",
        )
        adapter = CliLLMAdapter(CLI_REGISTRY["codex"])
        chunks = list(adapter.stream("test"))
        assert len(chunks) == 1
        assert chunks[0] == "fallback response"

    @patch("shutil.which", return_value="/usr/bin/claude")
    @patch("subprocess.Popen")
    def test_streaming_tool_yields_lines(self, mock_popen, _mock_which):
        """claude supports streaming — stream() should yield cleaned lines."""
        mock_proc = MagicMock()
        mock_proc.stdout = iter(["chunk 1\n", "chunk 2\n"])
        mock_proc.stderr = MagicMock()
        mock_proc.stderr.read.return_value = ""
        mock_proc.wait.return_value = None
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        adapter = CliLLMAdapter(CLI_REGISTRY["claude"])
        chunks = list(adapter.stream("test"))
        assert len(chunks) == 2
        assert chunks[0] == "chunk 1"
        assert chunks[1] == "chunk 2"

    @patch("shutil.which", return_value="/usr/bin/claude")
    @patch("subprocess.Popen")
    def test_streaming_failure(self, mock_popen, _mock_which):
        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.stderr = MagicMock()
        mock_proc.stderr.read.return_value = "error details"
        mock_proc.wait.return_value = None
        mock_proc.returncode = 1
        mock_popen.return_value = mock_proc

        adapter = CliLLMAdapter(CLI_REGISTRY["claude"])
        with pytest.raises(RuntimeError, match="failed"):
            list(adapter.stream("test"))

    @patch("shutil.which", return_value="/usr/bin/claude")
    @patch("subprocess.Popen")
    def test_streaming_timeout(self, mock_popen, _mock_which):
        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.stderr = MagicMock()
        mock_proc.wait.side_effect = subprocess.TimeoutExpired(cmd=["claude"], timeout=120)
        mock_proc.returncode = None
        mock_proc.kill = MagicMock()
        mock_popen.return_value = mock_proc

        adapter = CliLLMAdapter(CLI_REGISTRY["claude"])
        with pytest.raises(RuntimeError, match="timed out"):
            list(adapter.stream("test"))
        mock_proc.kill.assert_called_once()


# ---------------------------------------------------------------------------
# 4.6 — _validate_binary
# ---------------------------------------------------------------------------


class TestValidateBinary:
    @patch("shutil.which", return_value="/usr/bin/claude")
    def test_found(self, _mock_which):
        # Should not raise
        adapter = CliLLMAdapter(CLI_REGISTRY["claude"])
        assert adapter.config.binary == "claude"

    @patch("shutil.which", return_value=None)
    def test_not_found_raises(self, _mock_which):
        with pytest.raises(RuntimeError, match="not installed"):
            CliLLMAdapter(CLI_REGISTRY["claude"])


# ---------------------------------------------------------------------------
# 4.7 — build_llm("cli/claude") routes correctly
# ---------------------------------------------------------------------------


class TestBuildLlmCliRouting:
    @patch("shutil.which", return_value="/usr/bin/claude")
    def test_cli_claude_returns_adapter(self, _mock_which):
        provider = build_llm("cli/claude")
        assert isinstance(provider, CliLLMAdapter)
        assert provider.model == "cli/claude"

    @patch("shutil.which", return_value="/usr/bin/codex")
    def test_cli_codex_returns_adapter(self, _mock_which):
        provider = build_llm("cli/codex")
        assert isinstance(provider, CliLLMAdapter)

    @patch("shutil.which", return_value="/usr/bin/opencode")
    def test_cli_opencode_returns_adapter(self, _mock_which):
        provider = build_llm("cli/opencode")
        assert isinstance(provider, CliLLMAdapter)

    def test_unknown_cli_tool_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown CLI tool"):
            build_llm("cli/nonexistent")

    def test_unknown_cli_tool_lists_available(self):
        with pytest.raises(ValueError, match="claude"):
            build_llm("cli/nonexistent")

    @patch("shutil.which", return_value="/usr/bin/claude")
    def test_cli_adapter_satisfies_protocol(self, _mock_which):
        provider = build_llm("cli/claude")
        assert isinstance(provider, LLMProvider)

    @patch("shutil.which", return_value="/usr/bin/claude")
    def test_non_cli_model_still_returns_llm(self, _mock_which):
        """Ensure non-cli/ models still go through normal LiteLLM path."""
        # This should NOT create a CliLLMAdapter
        provider = build_llm("claude-haiku-3-5", api_key="fake-key")
        assert not isinstance(provider, CliLLMAdapter)
