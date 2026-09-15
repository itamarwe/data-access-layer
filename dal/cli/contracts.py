"""Common command result contract."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandOutcome:
    payload: object
    exit_code: int = 0
