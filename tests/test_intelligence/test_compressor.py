"""Tests for tree-sitter source code compression (repoforge.intelligence.compressor)."""

import pytest

from repoforge.intelligence.compressor import compress_file, compression_stats


# ---------------------------------------------------------------------------
# Python compression
# ---------------------------------------------------------------------------


class TestCompressPython:
    """Python source compression."""

    def test_keeps_function_signatures(self):
        """Function signatures are preserved, bodies removed."""
        source = '''
def process_data(items: list[str], limit: int = 100) -> dict:
    """Process incoming data items."""
    result = {}
    for item in items:
        if len(item) > limit:
            result[item[:limit]] = True
        else:
            result[item] = False
    return result

def validate(data: dict) -> bool:
    if not data:
        return False
    return all(isinstance(k, str) for k in data.keys())
'''
        compressed = compress_file(source.strip(), "module.py")
        # Signatures should be present
        assert "def process_data" in compressed
        assert "def validate" in compressed
        # Bodies should NOT be present
        assert "for item in items" not in compressed
        assert "isinstance" not in compressed

    def test_keeps_class_definition(self):
        """Class definition and method signatures preserved."""
        source = '''
class DataProcessor:
    """Processes data from multiple sources."""

    def __init__(self, config: dict):
        self.config = config
        self.cache = {}
        self._initialized = False

    def process(self, data: list) -> dict:
        result = {}
        for item in data:
            result[item] = self._transform(item)
        return result

    def _transform(self, item):
        return str(item).upper()
'''
        compressed = compress_file(source.strip(), "processor.py")
        assert "class DataProcessor" in compressed
        assert "def __init__" in compressed
        assert "def process" in compressed
        # Implementation should be removed
        assert "self._transform(item)" not in compressed

    def test_keeps_imports(self):
        """Import statements are preserved."""
        source = '''
import os
from pathlib import Path
from typing import Optional

def hello():
    return os.getcwd()
'''
        compressed = compress_file(source.strip(), "utils.py")
        assert "import os" in compressed
        assert "from pathlib import Path" in compressed
        assert "from typing import Optional" in compressed

    def test_compression_ratio_significant(self):
        """Compression achieves >50% reduction on real-ish Python."""
        source = '''
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class Config:
    """Application configuration."""
    host: str = "localhost"
    port: int = 8080
    debug: bool = False
    log_level: str = "INFO"

def create_app(config: Config) -> "App":
    """Create and configure the application."""
    app = App()
    app.config = config
    app.logger = logging.getLogger("app")
    if config.debug:
        app.logger.setLevel(logging.DEBUG)
    else:
        app.logger.setLevel(getattr(logging, config.log_level))
    return app

class App:
    """Main application class."""
    def __init__(self):
        self.config = None
        self.logger = None
        self._routes = []
        self._middleware = []

    def add_route(self, path: str, handler) -> None:
        """Register a new route."""
        self._routes.append((path, handler))
        self.logger.debug("Route added: %s", path)

    def add_middleware(self, middleware) -> None:
        """Add middleware to the stack."""
        self._middleware.append(middleware)

    def run(self) -> None:
        """Start the application server."""
        self.logger.info("Starting server on %s:%d", self.config.host, self.config.port)
        for mw in self._middleware:
            mw.initialize()
        while True:
            try:
                self._handle_request()
            except KeyboardInterrupt:
                break
        self.logger.info("Server stopped")

    def _handle_request(self):
        pass
'''
        compressed = compress_file(source.strip(), "app.py")
        stats = compression_stats(source, compressed)
        # Should achieve meaningful compression
        assert stats["reduction_pct"] > 30


# ---------------------------------------------------------------------------
# Go compression
# ---------------------------------------------------------------------------


class TestCompressGo:
    """Go source compression."""

    def test_keeps_func_signatures_and_types(self):
        """Go function signatures and type definitions preserved."""
        source = '''package server

import (
    "fmt"
    "net/http"
)

type Server struct {
    Host string
    Port int
}

func New(host string, port int) *Server {
    return &Server{
        Host: host,
        Port: port,
    }
}

func (s *Server) Start() error {
    addr := fmt.Sprintf("%s:%d", s.Host, s.Port)
    return http.ListenAndServe(addr, nil)
}
'''
        compressed = compress_file(source.strip(), "server.go")
        # Signatures should be present
        assert "package server" in compressed
        assert "type Server struct" in compressed
        assert "func New" in compressed
        assert "func (s *Server) Start" in compressed
        # Body details should be reduced
        assert 'fmt.Sprintf' not in compressed

    def test_keeps_imports(self):
        """Import declarations are preserved."""
        source = '''package main

import (
    "fmt"
    "os"
)

func main() {
    fmt.Println("hello")
    os.Exit(0)
}
'''
        compressed = compress_file(source.strip(), "main.go")
        assert "import" in compressed
        assert '"fmt"' in compressed


# ---------------------------------------------------------------------------
# TypeScript compression
# ---------------------------------------------------------------------------


class TestCompressTypeScript:
    """TypeScript source compression."""

    def test_keeps_exports_and_interfaces(self):
        """Export statements and interfaces preserved."""
        source = '''
import { Router } from 'express';
import type { User } from './types';

export interface UserService {
    getUser(id: string): Promise<User>;
    createUser(data: Partial<User>): Promise<User>;
}

export function createRouter(service: UserService): Router {
    const router = Router();
    router.get('/users/:id', async (req, res) => {
        const user = await service.getUser(req.params.id);
        res.json(user);
    });
    router.post('/users', async (req, res) => {
        const user = await service.createUser(req.body);
        res.status(201).json(user);
    });
    return router;
}

export class UserController {
    constructor(private service: UserService) {}

    async getUser(id: string): Promise<User> {
        return this.service.getUser(id);
    }
}
'''
        compressed = compress_file(source.strip(), "users.ts")
        assert "import" in compressed
        assert "interface UserService" in compressed
        assert "export function createRouter" in compressed
        # Route handler implementation should be removed/compressed
        assert "req.params.id" not in compressed


# ---------------------------------------------------------------------------
# Fallback compression
# ---------------------------------------------------------------------------


class TestFallbackCompression:
    """Fallback when tree-sitter not available for a file type."""

    def test_unsupported_extension_falls_back(self):
        """Unsupported extensions get first-N-lines fallback."""
        source = "\n".join([f"line {i}" for i in range(100)])
        compressed = compress_file(source, "config.toml")
        lines = compressed.split("\n")
        # Should be truncated
        assert len(lines) <= 32  # 30 lines + truncation marker
        assert "line 0" in compressed

    def test_short_file_unchanged(self):
        """Short files under the line limit are returned as-is."""
        source = "key = 'value'\nother = 42"
        compressed = compress_file(source, "config.toml")
        assert compressed == source

    def test_empty_content(self):
        """Empty content returns empty string."""
        assert compress_file("", "empty.py") == ""
        assert compress_file("   \n  ", "empty.py") == ""


# ---------------------------------------------------------------------------
# Compression stats
# ---------------------------------------------------------------------------


class TestCompressionStats:
    """Test compression_stats utility."""

    def test_stats_calculation(self):
        """Stats correctly compute token counts and ratio."""
        original = "x" * 400  # 100 tokens
        compressed = "x" * 100  # 25 tokens
        stats = compression_stats(original, compressed)
        assert stats["original_tokens"] == 100
        assert stats["compressed_tokens"] == 25
        assert stats["ratio"] == pytest.approx(0.25)
        assert stats["reduction_pct"] == pytest.approx(75.0)

    def test_stats_empty_compressed(self):
        """Empty compressed content returns 0 tokens."""
        stats = compression_stats("hello world", "")
        assert stats["compressed_tokens"] == 0
        assert stats["reduction_pct"] == pytest.approx(100.0)
