"""Versioned REST API and packaged curator application."""

from .app import create_app
from .config import ServerConfig

__all__ = ("ServerConfig", "create_app")
