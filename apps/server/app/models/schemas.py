"""Pydantic v2 request/response schemas for the RepoForge Web API.

All schemas use Python 3.12+ type syntax (str | None, list[...]).
Validators use Pydantic v2 @field_validator decorator.
"""

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# --- Auth ---


class UserInfo(BaseModel):
    """Lightweight user info returned from JWT validation."""

    github_id: int
    login: str
    avatar_url: str | None = None


class UserResponse(BaseModel):
    """Full user info returned from profile endpoints."""

    id: uuid.UUID
    github_login: str
    avatar_url: str | None = None
    email: str | None = None
    created_at: datetime


class AuthValidateResponse(BaseModel):
    """Response for POST /auth/validate."""

    user: UserInfo
    exp: int


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400


# --- Generation ---


class GenerateRequest(BaseModel):
    """Request to start a new generation job."""

    repo_url: str = Field(
        ..., min_length=1, max_length=500, description="GitHub repository URL"
    )
    mode: Literal["docs", "skills", "both"] = Field(
        ..., description="What to generate: docs, skills, or both"
    )
    model: str = Field(
        ..., min_length=1, max_length=100, description="LLM model identifier"
    )
    provider: str = Field(
        ..., min_length=1, max_length=50, description="LLM provider name"
    )
    language: str = Field(
        default="English", max_length=50, description="Output language"
    )
    complexity: str = Field(
        default="auto", max_length=20, description="Complexity level: auto, basic, intermediate, advanced"
    )
    options: dict | None = Field(
        default=None,
        description="Advanced options: targets, disclosure, theme, compress, etc.",
    )

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, v: str) -> str:
        """Validate that the URL is a valid GitHub repository URL."""
        pattern = r"^https://github\.com/[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+/?$"
        cleaned = v.rstrip("/").split("?")[0].split("#")[0]
        if not re.match(pattern, cleaned):
            raise ValueError(
                "Must be a valid GitHub repository URL (https://github.com/owner/repo)"
            )
        return cleaned


class GenerateResponse(BaseModel):
    """Response for POST /api/generate (202 Accepted)."""

    generation_id: uuid.UUID
    status: str = "queued"
    created_at: datetime


class GenerationDetail(BaseModel):
    """Full generation record for detail views."""

    id: uuid.UUID
    user_id: uuid.UUID
    repo_url: str
    repo_name: str
    repo_default_branch: str | None = None
    mode: str
    status: str
    config: dict | None = None
    result_metadata: dict | None = None
    files_generated: int | None = None
    total_tokens: int | None = None
    total_duration_ms: int | None = None
    quality_score: float | None = None
    error_message: str | None = None
    error_id: str | None = None
    artifact_path: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class GenerationListResponse(BaseModel):
    """Paginated list of generations."""

    items: list[GenerationDetail]
    total: int
    page: int
    per_page: int
    pages: int


# --- Provider Keys ---


class ProviderKeyCreate(BaseModel):
    """Request to create or update a provider key."""

    provider: str = Field(..., min_length=1, max_length=50)
    api_key: str = Field(..., min_length=1)
    model_id: str | None = Field(default=None, max_length=255)
    storage: Literal["persistent", "session"] = "persistent"


class ProviderKeyResponse(BaseModel):
    """Response for provider key (API key is masked)."""

    id: uuid.UUID | None = None
    provider: str
    key_hint: str
    model_id: str | None = None
    is_validated: bool = False
    validated_at: datetime | None = None
    created_at: datetime | None = None
    storage: Literal["persistent", "session"] = "persistent"


class ProviderKeyValidateRequest(BaseModel):
    """Request to validate a provider key without storing."""

    provider: str = Field(..., min_length=1, max_length=50)
    api_key: str = Field(..., min_length=1)


class ProviderKeyValidateResponse(BaseModel):
    """Response for key validation."""

    valid: bool
    provider: str


# --- Health ---


class HealthResponse(BaseModel):
    """Simple health check response."""

    status: str = "ok"
    version: str = "0.1.0"


class HealthDetailedResponse(BaseModel):
    """Detailed health check response with system status."""

    status: str
    uptime_seconds: int
    checks: dict
    active_generations: int
    response_ms: int


# --- Errors ---


class ErrorResponse(BaseModel):
    """Standard error response format with optional correlation ID."""

    error: str
    message: str
    error_id: str | None = None
