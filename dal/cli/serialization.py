"""JSON transport for CLI results."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Mapping


def dumps(value: object) -> str:
    return json.dumps(_value(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _value(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _value(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_value(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value
