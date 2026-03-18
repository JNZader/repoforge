"""ProviderKey ORM model for encrypted LLM provider API keys.

Each user can have one key per provider (e.g. anthropic, openai, groq).
Keys are stored encrypted with AES-256-GCM using per-user derived keys.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class ProviderKey(Base):
    """Encrypted API key for an LLM provider, scoped to a user."""

    __tablename__ = "provider_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_provider_keys_user_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    encrypted_api_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_hint: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Masked key hint, e.g. 'sk-...a3Fx'"
    )
    model_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="Preferred model for this provider"
    )
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="provider_keys")  # noqa: F821

    def __repr__(self) -> str:
        return f"<ProviderKey provider={self.provider!r} user_id={self.user_id!r}>"
