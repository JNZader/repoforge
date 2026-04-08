"""
cli_adapter.py - CLI-based LLM provider adapter.

Wraps locally installed CLI tools (claude, codex, opencode) as LLMProvider
implementations via subprocess. Each tool is described by a CliToolConfig
entry in CLI_REGISTRY.

Usage via build_llm():
    llm = build_llm("cli/claude")
    response = llm.complete("Explain monads")
"""

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Iterator, Optional

# ---------------------------------------------------------------------------
# ANSI escape stripper (shared across all tools)
# ---------------------------------------------------------------------------

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


# ---------------------------------------------------------------------------
# Tool configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CliToolConfig:
    """Immutable configuration describing how to invoke a CLI LLM tool."""

    binary: str
    prompt_mode: str  # "arg" (positional last arg) or "stdin"
    cmd_template: list[str] = field(default_factory=list)
    system_flag: Optional[str] = None
    stream_args: Optional[list[str]] = None
    supports_stream: bool = False
    output_patterns: list[re.Pattern] = field(default_factory=list)  # type: ignore[type-arg]
    timeout: int = 120


# ---------------------------------------------------------------------------
# Registry — one entry per supported CLI tool
# ---------------------------------------------------------------------------

CLI_REGISTRY: dict[str, CliToolConfig] = {
    "claude": CliToolConfig(
        binary="claude",
        prompt_mode="arg",
        cmd_template=["-p", "--output-format", "text", "--no-input"],
        system_flag="--system-prompt",
        stream_args=None,
        supports_stream=True,
        output_patterns=[],
    ),
    "codex": CliToolConfig(
        binary="codex",
        prompt_mode="arg",
        cmd_template=["exec", "--output-last-message", "/dev/stdout"],
        system_flag=None,
        supports_stream=False,
        output_patterns=[re.compile(r"^\x1b\[.*?m")],
    ),
    "opencode": CliToolConfig(
        binary="opencode",
        prompt_mode="arg",
        cmd_template=["run", "--format", "default"],
        system_flag=None,
        supports_stream=False,
        output_patterns=[re.compile(r"^[▄█▀░▒▓]+")],
    ),
}


# ---------------------------------------------------------------------------
# Output sanitizer
# ---------------------------------------------------------------------------

def sanitize_output(text: str, tool_patterns: Optional[list[re.Pattern]] = None) -> str:  # type: ignore[type-arg]
    """Strip ANSI codes, tool-specific noise patterns, and whitespace."""
    text = _ANSI_RE.sub("", text)
    if tool_patterns:
        for pattern in tool_patterns:
            text = pattern.sub("", text)
    return text.strip()


# ---------------------------------------------------------------------------
# CLI LLM Adapter
# ---------------------------------------------------------------------------

class CliLLMAdapter:
    """LLM provider that delegates to a CLI tool via subprocess."""

    def __init__(self, config: CliToolConfig, timeout: int = 120) -> None:
        self.config = config
        self.model = f"cli/{config.binary}"
        self.timeout = timeout
        self._validate_binary()

    # -- LLMProvider interface --

    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        """Single-shot completion via subprocess.run."""
        cmd = self._build_command(prompt, system)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"CLI tool '{self.config.binary}' failed "
                    f"(exit {result.returncode}): "
                    f"{result.stderr.strip()[:500]}"
                )
            return sanitize_output(result.stdout, self.config.output_patterns)
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"CLI tool '{self.config.binary}' timed out after {self.timeout}s"
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"CLI tool '{self.config.binary}' not found. Install it first."
            )

    def stream(self, prompt: str, system: Optional[str] = None) -> Iterator[str]:
        """Streaming completion. Falls back to complete() for non-streaming tools."""
        if not self.config.supports_stream:
            yield self.complete(prompt, system)
            return

        cmd = self._build_command(prompt, system, stream=True)
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        try:
            assert proc.stdout is not None  # for type checker
            for line in proc.stdout:
                cleaned = sanitize_output(line, self.config.output_patterns)
                if cleaned:
                    yield cleaned
            proc.wait(timeout=self.timeout)
            if proc.returncode != 0:
                stderr = proc.stderr.read() if proc.stderr else ""
                raise RuntimeError(
                    f"CLI tool '{self.config.binary}' failed "
                    f"(exit {proc.returncode}): {stderr.strip()[:500]}"
                )
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError(
                f"CLI tool '{self.config.binary}' timed out after {self.timeout}s"
            )

    # -- Internal helpers --

    def _build_command(
        self, prompt: str, system: Optional[str] = None, stream: bool = False,
    ) -> list[str]:
        """Assemble the subprocess argument list from config."""
        if stream and self.config.stream_args:
            cmd = [self.config.binary] + list(self.config.stream_args)
        else:
            cmd = [self.config.binary] + list(self.config.cmd_template)

        if system and self.config.system_flag:
            cmd.extend([self.config.system_flag, system])
        elif system:
            # No system flag — prepend system prompt to user prompt
            prompt = f"System: {system}\n\n{prompt}"

        cmd.append(prompt)
        return cmd

    def _validate_binary(self) -> None:
        """Ensure the CLI tool is installed and in PATH."""
        if not shutil.which(self.config.binary):
            raise RuntimeError(
                f"CLI tool '{self.config.binary}' is not installed or not in PATH. "
                f"Install it before using 'cli/{self.config.binary}' as a model."
            )
