"""Operational health and revision routes."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends

from ..dependencies import services
from ..schemas import HealthView, RevisionView
from ..security import authorize
from ..services import APIServices

router = APIRouter(prefix="/api/v1", dependencies=[Depends(authorize)])
Services = Annotated[APIServices, Depends(services)]


@router.get("/health", response_model=HealthView, operation_id="inspectHealth")
def health(service: Services) -> HealthView:
    result = service.health()
    return HealthView(
        healthy=result.healthy,
        failures=[asdict(issue) for issue in result.failures],
        gaps=[asdict(issue) for issue in result.gaps],
        checks=list(result.checks),
    )


@router.get("/revisions", response_model=RevisionView, operation_id="getRevisions")
def revisions(service: Services) -> RevisionView:
    return RevisionView(
        repository=service.curation.revision(),
        compiled=service.compiled_revision(),
    )
