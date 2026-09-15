"""Immutable values used by evidence records."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import TypeAlias, Union, cast

JsonScalar: TypeAlias = None | bool | int | float | str
FrozenJson: TypeAlias = Union[JsonScalar, tuple["FrozenJson", ...], "FrozenObject"]


@dataclass(frozen=True)
class FrozenObject(Mapping[str, FrozenJson]):
    """An insertion-ordered, immutable JSON object."""

    entries: tuple[tuple[str, FrozenJson], ...]

    def __getitem__(self, key: str) -> FrozenJson:
        for candidate, value in self.entries:
            if candidate == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self.entries)

    def __len__(self) -> int:
        return len(self.entries)


def freeze_json(value: object) -> FrozenJson:
    """Recursively copy a validated JSON value into immutable containers."""
    if isinstance(value, Mapping):
        return FrozenObject(tuple(
            (cast(str, key), freeze_json(item)) for key, item in value.items()
        ))
    if isinstance(value, list | tuple):
        return tuple(freeze_json(item) for item in value)
    return cast(JsonScalar, value)
