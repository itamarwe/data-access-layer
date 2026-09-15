"""Compile native context files into immutable local query bundles."""

from .build import BuildResult, BundleBuilder, CompilationError
from .diagnostics import compilation_diagnostics
from .embedding import Embedder, FastEmbedder, embedding_health
from .extract import extract_records
from .model import CompiledLink, CompiledObject, CompilationRecords

__all__ = (
    "BuildResult", "BundleBuilder", "CompilationError", "CompiledLink",
    "CompiledObject", "CompilationRecords", "Embedder", "FastEmbedder",
    "compilation_diagnostics", "embedding_health", "extract_records",
)
