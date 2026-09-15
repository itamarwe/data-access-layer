"""Failures exposed by the file repository."""


class RepositoryError(RuntimeError):
    """Base class for deterministic repository failures."""


class RevisionConflict(RepositoryError):
    """The repository changed after the caller last read it."""


class RecordNotFound(RepositoryError):
    """The requested repository record does not exist."""


class RecordAlreadyExists(RepositoryError):
    """Creating the record would overwrite an existing file."""
