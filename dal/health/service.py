"""One deterministic health inspection over explicit local inputs."""

from __future__ import annotations

from dal.repository import repository_revision

from .authored import inspect_authored
from .bundle import inspect_bundle
from .compiled import expected_object_hashes
from .evidence import inspect_evidence
from .inputs import HealthRequest
from .model import HealthResult, health_result
from .physical import inspect_physical
from .joins import inspect_joins


def inspect_health(request: HealthRequest) -> HealthResult:
    failures, gaps, documents = inspect_authored(request.repository_root)
    physical_failures = []
    if request.physical_catalog is not None:
        physical_failures, physical_gaps = inspect_physical(
            documents, request.physical_catalog, request.now,
            request.thresholds.source_max_age,
        )
        failures.extend(physical_failures)
        gaps.extend(physical_gaps)
    if request.evidence_directory is not None:
        failures.extend(inspect_evidence(
            request.evidence_directory, request.now,
            request.thresholds.evidence_max_age,
        ))
    failures.extend(inspect_joins(documents, request.evidence_directory, physical_failures))
    if request.active_bundle is not None:
        expected_objects = expected_object_hashes(documents) if not failures else None
        failures.extend(inspect_bundle(
            request.active_bundle, repository_revision(request.repository_root),
            expected_objects,
        ))
    checks = [{"name": "authored", "performed": True}]
    for name, supplied in (("physical", request.physical_catalog),
                           ("evidence", request.evidence_directory),
                           ("bundle", request.active_bundle)):
        checks.append({"name": name, "performed": supplied is not None,
                       "reason": "supplied local input" if supplied is not None else "no input supplied; not checked"})
    return health_result(failures, gaps, checks)
