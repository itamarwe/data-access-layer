"""File-based persistence for authored DAL repositories."""

from .atomic import replace_texts
from .documents import encode_document, read_document, semantic_path, load_repository, semantic_files
from .errors import (
    RecordAlreadyExists, RecordNotFound, RepositoryError, RevisionConflict,
)
from .locking import repository_lock
from .revision import repository_revision, require_revision

__all__ = (
    "RecordAlreadyExists",
    "RecordNotFound",
    "RepositoryError",
    "RevisionConflict",
    "encode_document",
    "read_document",
    "replace_texts",
    "repository_lock",
    "repository_revision",
    "require_revision",
    "semantic_path",
    "load_repository",
    "semantic_files",
)
