"""In-memory session-scoped API key store.

Keys stored here are NEVER persisted to disk or database. They live only
in the process memory and are lost on server restart (by design).

Thread-safety is handled via asyncio.Lock.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Default TTL matches JWT expiration (24 hours)
_DEFAULT_TTL_SECONDS = 86400
# Cleanup runs every 5 minutes
CLEANUP_INTERVAL_SECONDS = 300


@dataclass(slots=True)
class SessionKeyEntry:
    """A single session-scoped API key."""

    api_key: str
    model_id: str | None
    created_at: float  # time.monotonic()
    ttl: float = _DEFAULT_TTL_SECONDS

    @property
    def is_expired(self) -> bool:
        return (time.monotonic() - self.created_at) >= self.ttl


class SessionKeyStore:
    """In-memory store for session-scoped provider API keys.

    Keyed by ``user_id -> provider -> SessionKeyEntry``.
    All public methods are coroutine-safe via an internal asyncio.Lock.
    """

    def __init__(self, ttl: float = _DEFAULT_TTL_SECONDS) -> None:
        self._store: dict[str, dict[str, SessionKeyEntry]] = {}
        self._lock = asyncio.Lock()
        self._ttl = ttl

    async def set_key(
        self,
        user_id: str,
        provider: str,
        api_key: str,
        model_id: str | None = None,
    ) -> SessionKeyEntry:
        """Store a session key for the given user and provider.

        Overwrites any existing key for the same (user, provider) pair.
        """
        entry = SessionKeyEntry(
            api_key=api_key,
            model_id=model_id,
            created_at=time.monotonic(),
            ttl=self._ttl,
        )
        async with self._lock:
            if user_id not in self._store:
                self._store[user_id] = {}
            self._store[user_id][provider] = entry
        logger.debug("Session key set for user=%s provider=%s", user_id, provider)
        return entry

    async def get_key(self, user_id: str, provider: str) -> SessionKeyEntry | None:
        """Return the session key entry, or None if absent/expired."""
        async with self._lock:
            user_keys = self._store.get(user_id)
            if user_keys is None:
                return None
            entry = user_keys.get(provider)
            if entry is None:
                return None
            if entry.is_expired:
                del user_keys[provider]
                if not user_keys:
                    del self._store[user_id]
                return None
            return entry

    async def get_all_keys(self, user_id: str) -> dict[str, SessionKeyEntry]:
        """Return all non-expired session keys for a user."""
        result: dict[str, SessionKeyEntry] = {}
        async with self._lock:
            user_keys = self._store.get(user_id)
            if user_keys is None:
                return result
            expired: list[str] = []
            for provider, entry in user_keys.items():
                if entry.is_expired:
                    expired.append(provider)
                else:
                    result[provider] = entry
            for provider in expired:
                del user_keys[provider]
            if not user_keys:
                del self._store[user_id]
        return result

    async def delete_key(self, user_id: str, provider: str) -> bool:
        """Delete a session key. Returns True if it existed."""
        async with self._lock:
            user_keys = self._store.get(user_id)
            if user_keys is None:
                return False
            if provider not in user_keys:
                return False
            del user_keys[provider]
            if not user_keys:
                del self._store[user_id]
        logger.debug("Session key deleted for user=%s provider=%s", user_id, provider)
        return True

    async def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns the count of removed entries."""
        removed = 0
        async with self._lock:
            empty_users: list[str] = []
            for user_id, user_keys in self._store.items():
                expired = [p for p, e in user_keys.items() if e.is_expired]
                for provider in expired:
                    del user_keys[provider]
                    removed += 1
                if not user_keys:
                    empty_users.append(user_id)
            for user_id in empty_users:
                del self._store[user_id]
        if removed:
            logger.info("Session key cleanup: removed %d expired entries", removed)
        return removed

    async def count(self) -> int:
        """Return the total number of active (non-expired) session keys."""
        total = 0
        async with self._lock:
            for user_keys in self._store.values():
                total += sum(1 for e in user_keys.values() if not e.is_expired)
        return total


# Module-level singleton
session_key_store = SessionKeyStore()


async def session_key_cleanup_loop(store: SessionKeyStore | None = None) -> None:
    """Background loop that periodically cleans up expired session keys.

    Runs indefinitely — designed to be launched as an asyncio task.
    """
    target = store or session_key_store
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        try:
            await target.cleanup_expired()
        except Exception:
            logger.exception("Error during session key cleanup")
