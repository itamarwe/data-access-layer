"""Server configuration with an explicit remote-access boundary."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ServerConfig:
    repository_root: Path
    bundle: Path
    host: str = "127.0.0.1"
    port: int = 8765
    allow_remote: bool = False
    auth_token: str | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.port <= 65_535:
            raise ValueError("port must be between 1 and 65535")
        if not _loopback(self.host):
            if not self.allow_remote:
                raise ValueError("non-loopback binding requires --allow-remote")
            if not self.auth_token:
                raise ValueError("non-loopback binding requires an authentication token")


def _loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
