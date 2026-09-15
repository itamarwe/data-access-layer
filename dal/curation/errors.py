"""Failures in proposal and publication workflows."""

from __future__ import annotations

from dal.model import Diagnostic


class CurationError(RuntimeError):
    """A curation request is unsafe or violates its lifecycle."""


class CanonicalValidationError(CurationError):
    """A proposed document does not satisfy the complete canonical contract."""

    def __init__(self, diagnostics: tuple[Diagnostic, ...]):
        self.diagnostics = diagnostics
        summary = "; ".join(
            f"{item.pointer}: {item.message}" for item in diagnostics
        )
        super().__init__(summary)
