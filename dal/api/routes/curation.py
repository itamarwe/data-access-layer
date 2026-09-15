"""Proposal lifecycle routes; every mutation is revision checked."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from dal.curation import CurationResult

from ..dependencies import services
from ..schemas import DecisionBody, ProposalBody
from ..security import authorize, expected_revision
from ..services import APIServices

router = APIRouter(prefix="/api/v1/proposals", dependencies=[Depends(authorize)])
Services = Annotated[APIServices, Depends(services)]
Revision = Annotated[str, Depends(expected_revision)]


@router.get("", operation_id="listProposals")
def list_proposals(
    service: Services,
    status: Annotated[Literal["open", "published", "dismissed"] | None, Query()] = None,
) -> tuple[dict[str, object], ...]:
    return service.curation.list(status)


@router.get("/{proposal_id}", operation_id="getProposal")
def get_proposal(proposal_id: str, service: Services) -> dict[str, object]:
    return service.curation.get(proposal_id)


@router.post("", response_model=CurationResult, status_code=201, operation_id="createProposal")
def create_proposal(
    body: ProposalBody, service: Services, revision: Revision,
) -> CurationResult:
    return service.curation.create(
        body.proposal.model_dump(exclude_unset=True), expected_revision=revision,
    )


@router.post("/{proposal_id}/publish", response_model=CurationResult, operation_id="publishProposal")
def publish_proposal(
    proposal_id: str, body: DecisionBody, service: Services, revision: Revision,
) -> CurationResult:
    return service.curation.publish(
        proposal_id, expected_revision=revision,
        decided_by=body.decided_by, reason=body.reason,
    )


@router.post("/{proposal_id}/dismiss", response_model=CurationResult, operation_id="dismissProposal")
def dismiss_proposal(
    proposal_id: str, body: DecisionBody, service: Services, revision: Revision,
) -> CurationResult:
    return service.curation.dismiss(
        proposal_id, expected_revision=revision,
        decided_by=body.decided_by, reason=body.reason,
    )


@router.post(
    "/{proposal_id}/deprecate", response_model=CurationResult,
    operation_id="deprecateProposal",
)
def deprecate_proposal(
    proposal_id: str, body: DecisionBody, service: Services, revision: Revision,
) -> CurationResult:
    return service.curation.deprecate(
        proposal_id, expected_revision=revision,
        decided_by=body.decided_by, reason=body.reason,
    )
