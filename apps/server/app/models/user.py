"""User ORM model (GitHub OAuth).

Stores GitHub-authenticated users with their profile info and
optionally their encrypted GitHub OAuth token for private repo access.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class User(Base):
    """GitHub-authenticated user."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    github_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    github_login: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_token: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True, doc="Encrypted GitHub OAuth token for private repo access"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    provider_keys: Mapped[list["ProviderKey"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    generations: Mapped[list["Generation"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    usage_stats: Mapped[list["UsageStat"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User github_login={self.github_login!r}>"
