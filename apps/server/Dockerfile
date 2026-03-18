# ============================================================
# Stage 1: Builder — install dependencies
# ============================================================
FROM python:3.12-slim AS builder

WORKDIR /build

# Install system deps for building cryptography / asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev git && \
    rm -rf /var/lib/apt/lists/*

# Copy repoforge core (needed as dependency)
COPY pyproject.toml README.md /build/
COPY repoforge/ /build/repoforge/

# Copy server requirements and install all deps
COPY apps/server/requirements.txt /build/apps/server/requirements.txt
RUN pip install --no-cache-dir --prefix=/install \
    -r /build/apps/server/requirements.txt \
    /build/

# ============================================================
# Stage 2: Runtime — slim image
# ============================================================
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install only runtime libs: libpq (asyncpg), curl (healthcheck),
# git (repo cloning), ripgrep (repoforge scanner)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl git ripgrep && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Copy installed Python packages
COPY --from=builder /install /usr/local

# Copy repoforge core (needed for runtime imports)
COPY repoforge/ /app/repoforge/
COPY pyproject.toml /app/pyproject.toml

# Copy server application code
COPY apps/server/app/ /app/app/

# Copy alembic migration files
COPY apps/server/alembic.ini /app/alembic.ini
COPY apps/server/alembic/ /app/alembic/

# Copy startup script
COPY apps/server/start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Create clone directory with correct permissions
RUN mkdir -p /tmp/repoforge-clones && chown appuser:appuser /tmp/repoforge-clones

# Switch to non-root user
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/start.sh"]
