"""UsageStat ORM model for daily aggregated usage analytics.

One row per user per day, updated after each generation completes.
Used to power the analytics dashboard charts.
"""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class UsageStat(Base):
    """Daily aggregated usage statistics per user."""

    __tablename__ = "usage_stats"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_usage_stats_user_date"),
        Index("ix_usage_stats_user_id_date", "user_id", "date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    generations_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_total_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="usage_stats")  # noqa: F821

    def __repr__(self) -> str:
        return f"<UsageStat user_id={self.user_id!r} date={self.date!r}>"
