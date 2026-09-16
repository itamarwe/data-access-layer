"""Search, typed resources, and bounded context trails."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from dal.application.models import DEFAULT_TOKEN_BUDGET, CatalogObject, TableDetail, Connections, SearchOptions, SearchResponse

from ..dependencies import services
from ..schemas import EvidenceList, NeighborList, ResourceKind, ResourceList
from ..security import authorize
from ..services import APIServices

router = APIRouter(prefix="/api/v1", dependencies=[Depends(authorize)])
Services = Annotated[APIServices, Depends(services)]


@router.get("/search", response_model=SearchResponse, operation_id="searchCatalog")
def search_catalog(
    service: Services,
    q: Annotated[str, Query(min_length=1, description="Natural-language context need")],
    kind: ResourceKind | None = None,
    lexical: Annotated[float | None, Query(ge=0)] = None,
    embedding: Annotated[float | None, Query(ge=0)] = None,
    graph: Annotated[float | None, Query(ge=0)] = None,
    evidence: Annotated[float | None, Query(ge=0)] = None,
    publication: Annotated[float | None, Query(ge=0)] = None,
    token_budget: Annotated[int, Query(ge=400, le=8_000)] = DEFAULT_TOKEN_BUDGET,
    include_deprecated: bool = False,
    parent_id: str | None = None,
) -> SearchResponse:
    weights = {
        name: value for name, value in {
            "lexical": lexical, "embedding": embedding, "graph": graph,
            "evidence": evidence, "publication": publication,
        }.items() if value is not None
    }
    return service.catalog.search(
        q, kind=kind.value if kind else None, weights=weights,
        options=SearchOptions(token_budget=token_budget, include_deprecated=include_deprecated),
        parent_id=parent_id,
    )


@router.get("/resources/{kind}", response_model=ResourceList, operation_id="listResources")
def list_resources(
    kind: ResourceKind,
    service: Services,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_deprecated: bool = False,
    parent_id: str | None = None,
    referenced_object_id: str | None = None,
) -> ResourceList:
    found = service.catalog.list(kind.value, limit=limit, offset=offset, include_deprecated=include_deprecated,
                                 parent_id=parent_id, referenced_object_id=referenced_object_id)
    return ResourceList(
        kind=kind, results=[asdict(item) for item in found], limit=limit, offset=offset,
    )


@router.get("/graph/objects", response_model=list[CatalogObject], operation_id="resolveResources")
def resolve_resources(
    service: Services,
    object_id: Annotated[list[str], Query(min_length=1, max_length=100)],
) -> tuple[CatalogObject, ...]:
    return service.catalog.resolve(object_id)


@router.get(
    "/resources/{kind}/{object_id:path}", response_model=TableDetail | CatalogObject,
    responses={404: {"description": "Resource not found"}}, operation_id="getResource",
)
def get_resource(kind: ResourceKind, object_id: str, service: Services,
                 columns_limit: Annotated[int, Query(ge=1, le=100)] = 20,
                 columns_offset: Annotated[int, Query(ge=0)] = 0):
    from fastapi import HTTPException

    found = (service.catalog.table_detail(object_id, limit=columns_limit, offset=columns_offset)
             if kind.value == "table" else service.catalog.get(kind.value, object_id))
    if found is None:
        raise HTTPException(404, "Resource not found")
    return found


@router.get("/graph/neighbors", response_model=NeighborList, operation_id="listNeighbors")
def graph_neighbors(
    service: Services,
    object_id: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> NeighborList:
    found = service.catalog.neighbors(object_id, limit=limit)
    return NeighborList(object_id=object_id, neighbors=[asdict(item) for item in found])


@router.get("/graph/connections", response_model=Connections, operation_id="listConnections")
def graph_connections(
    service: Services,
    object_id: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Connections:
    return service.catalog.connections(object_id, limit=limit)


@router.get("/graph/evidence", response_model=EvidenceList, operation_id="listEvidence")
def graph_evidence(
    service: Services,
    object_id: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    column_id: str | None = None,
    claim_path: str | None = None,
) -> EvidenceList:
    found = service.catalog.evidence(object_id, limit=limit, column_id=column_id, claim_path=claim_path)
    return EvidenceList(object_id=object_id, evidence=[asdict(item) for item in found])
