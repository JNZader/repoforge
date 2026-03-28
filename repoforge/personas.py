"""Persona-adaptive documentation — same codebase, different audience depth.

Each persona modifies the system and user prompts to tailor documentation
for a specific audience: beginners get step-by-step guides, architects
get design tradeoffs, API consumers get endpoint references, contributors
get development workflows.

Usage:
    from repoforge.personas import apply_persona
    prompts = apply_persona("beginner", system_prompt, user_prompt)
    # prompts["system"], prompts["user"]

    # Or use --persona flag in CLI:
    # repoforge docs --persona beginner
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Persona:
    """A documentation audience persona."""

    name: str
    description: str
    system_modifier: str
    focus_areas: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Built-in personas
# ---------------------------------------------------------------------------

PERSONAS: dict[str, Persona] = {
    "beginner": Persona(
        name="beginner",
        description="New to the project and possibly the tech stack",
        system_modifier=(
            "Your audience is a BEGINNER developer who is new to this project "
            "and may be unfamiliar with the technology stack. Write step-by-step "
            "instructions with simple language. Explain jargon when first used. "
            "Include complete, runnable code examples with expected output. "
            "Assume nothing about prior knowledge."
        ),
        focus_areas=[
            "Step-by-step setup instructions",
            "Simple, complete code examples",
            "Glossary of terms",
            "Common mistakes and how to fix them",
            "Visual diagrams for concepts",
        ],
        avoid=[
            "Advanced optimization patterns",
            "Internal implementation details",
            "Performance tuning",
        ],
    ),
    "contributor": Persona(
        name="contributor",
        description="Developer who wants to contribute code to the project",
        system_modifier=(
            "Your audience is a CONTRIBUTOR — a developer who wants to modify "
            "or extend this project's code. Focus on development workflow, testing "
            "patterns, code conventions, and how to add new features. Include "
            "the architecture context needed to make changes safely."
        ),
        focus_areas=[
            "Development environment setup",
            "Code conventions and style guide",
            "Testing strategy and how to write tests",
            "Module boundaries and where to add new code",
            "PR and review workflow",
        ],
        avoid=[
            "Basic installation for end users",
            "Marketing language",
        ],
    ),
    "architect": Persona(
        name="architect",
        description="Senior engineer evaluating design decisions and tradeoffs",
        system_modifier=(
            "Your audience is a SENIOR ARCHITECT evaluating this project's design. "
            "Focus on architecture patterns, design tradeoffs, scalability decisions, "
            "and technical debt. Use precise technical language. Include dependency "
            "diagrams, data flow analysis, and comparison with alternative approaches."
        ),
        focus_areas=[
            "Architecture patterns used and why",
            "Design tradeoffs and alternatives considered",
            "Scalability and performance characteristics",
            "Dependency analysis and coupling",
            "Technical debt and improvement opportunities",
        ],
        avoid=[
            "Basic getting-started content",
            "Step-by-step tutorials",
            "Boilerplate explanations",
        ],
    ),
    "api-consumer": Persona(
        name="api-consumer",
        description="Developer integrating with this project's API",
        system_modifier=(
            "Your audience is an API CONSUMER — a developer building on top of "
            "this project's public interface. Focus on API endpoints, request/response "
            "formats, authentication, error handling, and integration examples. "
            "Every endpoint must have a curl/code example."
        ),
        focus_areas=[
            "Complete API reference with examples",
            "Authentication and authorization",
            "Error codes and handling",
            "Rate limits and pagination",
            "SDK/client library usage",
        ],
        avoid=[
            "Internal implementation details",
            "Database schema internals",
            "Deployment/infrastructure",
        ],
    ),
}


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def get_persona(name: str) -> Persona:
    """Get a persona by name. Raises ValueError if unknown."""
    persona = PERSONAS.get(name)
    if persona is None:
        available = ", ".join(sorted(PERSONAS.keys()))
        raise ValueError(f"Unknown persona '{name}'. Available: {available}")
    return persona


def apply_persona(
    persona_name: str | None,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, str]:
    """Apply a persona's modifiers to system and user prompts.

    If persona_name is None, returns prompts unchanged.

    Returns:
        {"system": modified_system, "user": modified_user}
    """
    if persona_name is None:
        return {"system": system_prompt, "user": user_prompt}

    persona = get_persona(persona_name)

    # Modify system prompt: append persona context
    modified_system = (
        f"{system_prompt}\n\n"
        f"AUDIENCE PERSONA: {persona.description}\n"
        f"{persona.system_modifier}\n\n"
        f"Focus on: {', '.join(persona.focus_areas)}\n"
    )
    if persona.avoid:
        modified_system += f"Avoid: {', '.join(persona.avoid)}\n"

    # Modify user prompt: add focus instruction
    modified_user = (
        f"{user_prompt}\n\n"
        f"IMPORTANT: Tailor this chapter for a {persona.name} audience. "
        f"Focus on: {', '.join(persona.focus_areas[:3])}."
    )

    return {"system": modified_system, "user": modified_user}
