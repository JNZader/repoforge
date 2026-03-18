"""Alembic env.py — async migration runner for RepoForge server."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings

# Import all models so Alembic sees them for autogenerate
from app.models.database import Base
from app.models.user import User  # noqa: F401
from app.models.provider_key import ProviderKey  # noqa: F401
from app.models.generation import Generation, GenerationEvent  # noqa: F401
from app.models.usage_stat import UsageStat  # noqa: F401

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# MetaData for autogenerate support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL without connecting."""
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # noqa: ANN001
    """Run migrations with a synchronous connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using an async engine."""
    connectable = create_async_engine(settings.DATABASE_URL)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
