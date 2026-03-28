"""Config profiles — pre-configured settings for common project types.

Profiles bundle project_type, persona, complexity, and recommended
chapters into a single `--profile` flag for quick setup.

Usage:
    repoforge docs --profile fastapi
    repoforge docs --profile cli
    repoforge docs --profile library
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ProfileConfig:
    """Pre-configured settings for a project type."""

    name: str
    project_type: str
    description: str
    default_persona: str | None = None
    default_language: str = "English"
    recommended_chapters: list[str] = field(default_factory=list)
    extra_config: dict = field(default_factory=dict)


PROFILES: dict[str, ProfileConfig] = {
    "fastapi": ProfileConfig(
        name="fastapi",
        project_type="web_service",
        description="FastAPI/Flask/Django REST API backend",
        default_persona="api-consumer",
        recommended_chapters=[
            "01-overview.md", "02-quickstart.md", "03-architecture.md",
            "04-core-mechanisms.md", "05-data-models.md", "06-api-reference.md",
            "07-dev-guide.md",
        ],
    ),
    "cli": ProfileConfig(
        name="cli",
        project_type="cli_tool",
        description="Command-line tool or CLI application",
        default_persona="beginner",
        recommended_chapters=[
            "01-overview.md", "02-quickstart.md", "03-architecture.md",
            "04-core-mechanisms.md", "05-commands.md", "06-config.md",
            "07-dev-guide.md",
        ],
    ),
    "library": ProfileConfig(
        name="library",
        project_type="library_sdk",
        description="Reusable library, SDK, or package",
        default_persona="api-consumer",
        recommended_chapters=[
            "01-overview.md", "02-quickstart.md", "03-architecture.md",
            "04-core-mechanisms.md", "05-api-reference.md", "06-integration.md",
            "07-dev-guide.md",
        ],
    ),
    "monorepo": ProfileConfig(
        name="monorepo",
        project_type="monorepo",
        description="Multi-package or multi-service repository",
        default_persona="contributor",
        recommended_chapters=[
            "01-overview.md", "02-quickstart.md", "03-architecture.md",
            "04-core-mechanisms.md", "05-data-models.md", "06-api-reference.md",
            "06b-service-map.md", "07-dev-guide.md",
        ],
    ),
    "frontend": ProfileConfig(
        name="frontend",
        project_type="frontend_app",
        description="React/Vue/Angular/Svelte SPA",
        default_persona="contributor",
        recommended_chapters=[
            "01-overview.md", "02-quickstart.md", "03-architecture.md",
            "04-core-mechanisms.md", "05-components.md", "06-state.md",
            "07-dev-guide.md",
        ],
    ),
    "data": ProfileConfig(
        name="data",
        project_type="data_science",
        description="ML/data pipeline/notebooks project",
        default_persona="contributor",
        recommended_chapters=[
            "01-overview.md", "02-quickstart.md", "03-architecture.md",
            "04-data-pipeline.md", "05-models.md", "06-experiments.md",
            "07-dev-guide.md",
        ],
    ),
}


def get_profile(name: str) -> ProfileConfig:
    """Get a profile by name. Raises ValueError if unknown."""
    profile = PROFILES.get(name)
    if profile is None:
        available = ", ".join(sorted(PROFILES.keys()))
        raise ValueError(f"Unknown profile '{name}'. Available: {available}")
    return profile


def apply_profile(profile_name: str | None, config: dict) -> dict:
    """Apply a profile's defaults to a config dict. User values take precedence."""
    if profile_name is None:
        return config

    profile = get_profile(profile_name)
    result = dict(config)

    # Profile provides defaults — user config overrides
    result.setdefault("project_type", profile.project_type)
    result.setdefault("persona", profile.default_persona)
    result.setdefault("language", profile.default_language)
    result["recommended_chapters"] = profile.recommended_chapters

    return result
