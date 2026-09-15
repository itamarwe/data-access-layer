"""Search and catalog use cases over compiled DAL bundles."""

from .kinds import RESOURCE_KINDS
from .embedding import QueryEmbedder
from .models import RankingWeights, SearchOptions, SearchResponse
from .repository import BundleCatalog, BundleNotFoundError
from .service import CatalogService

__all__ = (
    "BundleCatalog", "BundleNotFoundError", "CatalogService", "QueryEmbedder",
    "RESOURCE_KINDS", "RankingWeights", "SearchOptions", "SearchResponse",
)
