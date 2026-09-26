"""Compare generated prose with the facts that grounded it.

Pass the facts that were placed in this chapter's context. A chapter is not
required to mention every fact in the repository, and this module will not
infer which of those it should have received.

Checked types are ``port``, ``endpoint``, ``db_table``, and ``env_var``.
A value is invented when the prose claims it and no passed fact has it.
A value is missing when a passed fact never appears in the prose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .facts import FactItem

_CHECKED = ("port", "endpoint", "db_table", "env_var")

# "port 7437", "listens on port 7437", "localhost:7437". A bare integer
# ("line 120", "18080") is not a port claim.
_PORT_CLAIM = re.compile(
    r"(?i)(?<!\d)(?:"
    r"(?:port|listen(?:s|ing)?|localhost|127\.0\.0\.1|0\.0\.0\.0)\s*[:=]?\s*(\d{2,5})"
    r"|:(\d{2,5})"
    r")(?!\d)"
)

_METHOD_ENDPOINT = re.compile(r"(?i)\b(GET|POST|PUT|DELETE|PATCH)\s+(/[A-Za-z0-9_/\-{}:.]+)")
_BARE_ENDPOINT = re.compile(r"(?<![A-Za-z0-9_./\-])(/(?:api|v\d+)/[A-Za-z0-9_/\-{}:.]+)")

_TABLE_CLAIM = re.compile(r"(?i)\btable\s+`?([A-Za-z_][A-Za-z0-9_]*)`?")

# Explicit env access, a backticked NAME, or an ALL_CAPS name that contains
# an underscore. Plain words such as HTTP or JSON are not env claims.
_ENV_CLAIM = re.compile(
    r"(?:process\.env\.|os\.getenv\(\s*[\"']|os\.environ(?:\.get)?\s*[\[(]\s*[\"'])"
    r"([A-Z][A-Z0-9_]{2,})"
    r"|`([A-Z][A-Z0-9_]{2,})`"
    r"|\b([A-Z][A-Z0-9]*_[A-Z0-9_]+)\b"
)

_PARAM = re.compile(r"\{[^}]+\}|:[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True, slots=True)
class FactualityReport:
    """Invented and missing claims, each ``type:value``."""

    invented: tuple[str, ...]
    missing: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.invented and not self.missing


def check_factuality(markdown: str, facts: list[FactItem]) -> FactualityReport:
    """Return invented and missing structural claims in ``markdown``."""
    grouped: dict[str, set[str]] = {kind: set() for kind in _CHECKED}
    for fact in facts:
        if fact.fact_type in grouped and fact.value:
            grouped[fact.fact_type].add(fact.value.strip())

    invented: list[str] = []
    missing: list[str] = []
    _ports(markdown, grouped["port"], invented, missing)
    _endpoints(markdown, grouped["endpoint"], invented, missing)
    _tables(markdown, grouped["db_table"], invented, missing)
    _env_vars(markdown, grouped["env_var"], invented, missing)
    return FactualityReport(tuple(invented), tuple(missing))


def invented_claim_block(markdown: str, facts: list[FactItem]) -> str | None:
    """Block a write when the prose invents a checked claim.

    Missing facts do not block. A chapter does not have to repeat every
    fact it was shown. An invented port, endpoint, table, or env var must
    not be written. Run this on the text that would hit disk, after the
    port rewrite.
    """
    report = check_factuality(markdown, facts)
    if not report.invented:
        return None
    return "factuality: " + ", ".join(report.invented)


def _ports(markdown: str, known: set[str], invented: list[str], missing: list[str]) -> None:
    claimed: set[str] = set()
    for match in _PORT_CLAIM.finditer(markdown):
        value = match.group(1) or match.group(2)
        if value:
            claimed.add(value)
    for value in sorted(claimed - known):
        invented.append(f"port:{value}")
    for value in sorted(known - claimed):
        missing.append(f"port:{value}")


def _split_endpoint(value: str) -> tuple[str | None, str]:
    parts = value.strip().split()
    if len(parts) >= 2 and parts[0].isalpha():
        return parts[0].upper(), _norm_path(parts[-1])
    return None, _norm_path(parts[-1] if parts else value)


def _norm_path(path: str) -> str:
    path = path.strip().rstrip("/")
    return _PARAM.sub(":param", path)


def _endpoints(markdown: str, known: set[str], invented: list[str], missing: list[str]) -> None:
    known_pairs = {_split_endpoint(value) for value in known}

    claimed: set[tuple[str | None, str]] = set()
    for match in _METHOD_ENDPOINT.finditer(markdown):
        claimed.add((match.group(1).upper(), _norm_path(match.group(2))))
    for match in _BARE_ENDPOINT.finditer(markdown):
        claimed.add((None, _norm_path(match.group(1))))

    for method, path in sorted(claimed, key=lambda item: (item[1], item[0] or "")):
        if _endpoint_covered(method, path, known_pairs):
            continue
        label = f"{method} {path}" if method else path
        invented.append(f"endpoint:{label}")

    claimed_paths = {path for _, path in claimed}
    for value in sorted(known):
        method, path = _split_endpoint(value)
        if not path:
            continue
        if method:
            present = (method, path) in claimed
        else:
            present = path in claimed_paths
        if not present:
            missing.append(f"endpoint:{value}")


def _endpoint_covered(
    method: str | None, path: str, known_pairs: set[tuple[str | None, str]]
) -> bool:
    if (method, path) in known_pairs or (None, path) in known_pairs:
        return True
    if method is None:
        return any(known_path == path for _, known_path in known_pairs)
    return False


def _tables(markdown: str, known: set[str], invented: list[str], missing: list[str]) -> None:
    claimed = {match.group(1) for match in _TABLE_CLAIM.finditer(markdown)}
    for name in sorted(claimed - known):
        invented.append(f"db_table:{name}")
    for name in sorted(known):
        if re.search(rf"\b{re.escape(name)}\b", markdown) is None:
            missing.append(f"db_table:{name}")


def _env_vars(markdown: str, known: set[str], invented: list[str], missing: list[str]) -> None:
    claimed: set[str] = set()
    for match in _ENV_CLAIM.finditer(markdown):
        value = match.group(1) or match.group(2) or match.group(3)
        if value:
            claimed.add(value)
    for name in sorted(claimed - known):
        invented.append(f"env_var:{name}")
    for name in sorted(known):
        if re.search(rf"\b{re.escape(name)}\b", markdown) is None:
            missing.append(f"env_var:{name}")
