"""Application settings — fail-fast on startup if required vars are missing.

Uses pydantic-settings to load from environment variables and .env file.
Required fields (no defaults) will raise a validation error immediately
on import, preventing the server from starting with bad configuration.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Server configuration via environment variables.

    Required variables will raise a validation error on startup if missing.
    Optional variables have sensible defaults for local development.
    """

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://repoforge:repoforge@localhost:5432/repoforge"

    # --- Auth / JWT ---
    JWT_SECRET: str  # REQUIRED — no default
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_SECONDS: int = 86400  # 24h

    # --- GitHub OAuth ---
    GITHUB_CLIENT_ID: str  # REQUIRED
    GITHUB_CLIENT_SECRET: str  # REQUIRED
    STATE_SECRET: str  # REQUIRED — HMAC key for OAuth state parameter

    # --- Frontend ---
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = ""  # If empty, derived from request for dev

    # --- Encryption ---
    ENCRYPTION_KEY: str  # REQUIRED — 64-char hex string (32 bytes) for AES-256-GCM

    # --- CORS ---
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:4173",
    ]

    # --- Server ---
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    DEBUG: bool = False

    # --- Generation ---
    MAX_CONCURRENT_GENERATIONS: int = 5
    GENERATION_TIMEOUT_MINUTES: int = 15
    CLONE_BASE_DIR: str = "/tmp/repoforge-clones"
    MAX_REPO_SIZE_MB: int = 500

    # --- Rate Limiting ---
    RATE_LIMIT_GENERATE_PER_HOUR: int = 20
    RATE_LIMIT_API_PER_MINUTE: int = 100
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10

    # --- Logging ---
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # "json" or "console"

    @field_validator("ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        """Ensure ENCRYPTION_KEY is a valid 64-char hex string (32 bytes)."""
        try:
            key_bytes = bytes.fromhex(v)
        except ValueError as exc:
            raise ValueError("ENCRYPTION_KEY must be a valid hex string") from exc
        if len(key_bytes) != 32:
            raise ValueError(
                f"ENCRYPTION_KEY must be a 64-char hex string (32 bytes), got {len(key_bytes)} bytes"
            )
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


# Fail-fast: if any REQUIRED field is missing, this crashes on import.
# The server will not start with invalid configuration.
settings = Settings()
