"""Optional proposal review for version-controlled catalog files."""

from __future__ import annotations

import argparse

from dal.curation import CurationService

from .contracts import CommandOutcome
from .files import read_document


def register(commands) -> None:
    proposal = commands.add_parser("proposal", help="Review and curate proposals.")
    proposal.add_argument("--repository", default=argparse.SUPPRESS)
    actions = proposal.add_subparsers(dest="proposal_action", required=True)
    listing = actions.add_parser("list")
    listing.add_argument("--status", choices=("open", "published", "dismissed"))
    listing.set_defaults(handler=run)
    get = actions.add_parser("get")
    get.add_argument("id")
    get.set_defaults(handler=run)
    create = actions.add_parser("create")
    create.add_argument("input")
    _revision(create)
    create.set_defaults(handler=run)
    for action in ("publish", "dismiss", "deprecate"):
        decision = actions.add_parser(action)
        decision.add_argument("id")
        _revision(decision)
        decision.add_argument("--decided-by")
        decision.add_argument("--reason")
        decision.set_defaults(handler=run)


def run(arguments: argparse.Namespace) -> CommandOutcome:
    service = CurationService(arguments.repository)
    action = arguments.proposal_action
    if action == "list":
        return CommandOutcome({
            "proposals": service.list(arguments.status),
            "repository_revision": service.revision(),
        })
    if action == "get":
        return CommandOutcome({
            "proposal": service.get(arguments.id),
            "repository_revision": service.revision(),
        })
    if action == "create":
        value = read_document(arguments.input)
        proposal = value.get("proposal", value)
        return CommandOutcome(service.create(
            proposal, expected_revision=arguments.expected_revision,
        ))
    operation = getattr(service, action)
    return CommandOutcome(operation(
        arguments.id,
        expected_revision=arguments.expected_revision,
        decided_by=arguments.decided_by,
        reason=arguments.reason,
    ))


def _revision(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--expected-revision", required=True,
        help="Required optimistic concurrency revision.",
    )
