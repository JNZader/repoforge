"""Generation and GenerationEvent ORM models.

Generation tracks a single documentation/skills generation run.
GenerationEvent stores SSE events for replay and debugging.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class Generation(Base):
    """One record per generation run (docs, skills, or both)."""

    __tablename__ = "generations"
    __table_args__ = (
        Index("ix_generations_user_id", "user_id"),
        Index("ix_generations_status", "status"),
        Index("ix_generations_created_at", "created_at", postgresql_using="btree"),
        Index("ix_generations_repo_name", "repo_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    repo_url: Mapped[str] = mapped_column(Text, nullable=False)
    repo_name: Mapped[str] = mapped_column(
        String(255), nullable=False, doc="owner/repo format"
    )
    repo_default_branch: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    mode: Mapped[str] = mapped_column(
        String(20), nullable=False, doc="docs | skills | both"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
        doc="queued | cloning | scanning | generating | completed | failed | cancelled",
    )

    # Configuration snapshot
    config: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, doc="{ model, provider, language, complexity, targets, ... }"
    )

    # Results (populated on completion)
    result_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, doc="{ chapters_generated, skills, complexity }"
    )
    files_generated: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Quality score (if skills were generated + scored)
    quality_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, doc="0.0 - 1.0 overall quality score"
    )

    # Error info
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_id: Mapped[str | None] = mapped_column(
        String(8), nullable=True, doc="Correlation ID for error tracking"
    )

    # ZIP artifact path
    artifact_path: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Path to ZIP artifact file"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="generations")  # noqa: F821
    events: Mapped[list["GenerationEvent"]] = relationship(
        back_populates="generation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Generation id={self.id!r} repo={self.repo_name!r} status={self.status!r}>"


class GenerationEvent(Base):
    """Event log entry for SSE replay and debugging."""

    __tablename__ = "generation_events"
    __table_args__ = (
        Index("ix_generation_events_generation_id", "generation_id"),
        Index("ix_generation_events_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generations.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False, doc="generation_started, chapter_started, etc."
    )
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, doc="Full event payload"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    generation: Mapped["Generation"] = relationship(back_populates="events")

    def __repr__(self) -> str:
        return f"<GenerationEvent type={self.event_type!r} gen_id={self.generation_id!r}>"
