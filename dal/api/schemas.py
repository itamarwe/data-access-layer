"""Closed HTTP request and response shapes not owned by domain services."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dal.application.models import CatalogObject, EvidenceSummary, GraphNeighbor


class ResourceKind(str, Enum):
    database = "database"
    table = "table"
    column = "column"
    join = "join"
    metric = "metric"
    entity = "entity"
    property = "property"
    relation = "relation"
    doctrine = "doctrine"
    gold_query = "gold_query"


class ResourceList(BaseModel):
    kind: ResourceKind
    results: list[CatalogObject]
    limit: int
    offset: int


class NeighborList(BaseModel):
    object_id: str
    neighbors: list[GraphNeighbor]


class EvidenceList(BaseModel):
    object_id: str
    evidence: list[EvidenceSummary]


class AddPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["add"]
    path: str = Field(pattern=r"^/")
    value: Any


class ReplacePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["replace"]
    path: str = Field(pattern=r"^/")
    value: Any


class RemovePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["remove"]
    path: str = Field(pattern=r"^/")


Patch = Annotated[AddPatch | ReplacePatch | RemovePatch, Field(discriminator="op")]


class ProposalTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document: str | None = Field(default=None, min_length=1)
    object_id: str = Field(min_length=1)


class Curator(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["curator"]
    id: str = Field(min_length=1)


class ProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^urn:dal:proposal:")
    status: Literal["open"]
    target: ProposalTarget
    base_revision: str = Field(pattern=r"^sha256:")
    patch: list[Patch] | None = Field(default=None, min_length=1)
    object: dict[str, Any] | None = None
    reason: str | None = Field(default=None, min_length=1)
    created_by: Curator | None = None

    @model_validator(mode="after")
    def one_change(self):
        if (self.patch is None) == (self.object is None):
            raise ValueError("provide exactly one of patch or object")
        return self


class ProposalBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal: ProposalInput


class DecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decided_by: str | None = Field(default=None, min_length=1)
    reason: str | None = Field(default=None, min_length=1)


class RevisionView(BaseModel):
    repository: str
    compiled: str | None


class HealthView(BaseModel):
    healthy: bool
    failures: list[dict[str, str]]
    gaps: list[dict[str, str]]
    checks: list[dict[str, Any]]
