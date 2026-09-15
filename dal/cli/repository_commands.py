"""Create and validate a native file-based context repository."""

from pathlib import Path

from dal.documents import dump_document
from dal.model import validate_document
from dal.repository import load_repository

from .contracts import CommandOutcome
from .files import read_document


def register(commands):
    init = commands.add_parser("init", help="Create an empty native context repository.")
    init.set_defaults(handler=initialize)
    validate = commands.add_parser("validate", help="Validate catalog files and cross-object references.")
    validate.add_argument("input", nargs="?")
    validate.set_defaults(handler=validate_repository)


def initialize(arguments):
    root = Path(arguments.repository)
    path = root / "semantic" / "catalog.yaml"
    if path.exists() or (path.parent.exists() and any(path.parent.iterdir())):
        raise ValueError("repository already contains semantic files")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as target:
        target.write(dump_document({"version": 1, "objects": []}))
    return CommandOutcome({"repository": str(root), "catalog": str(path),
                           "next_commands": ["dal validate", "dal build"]})


def validate_repository(arguments):
    document = read_document(arguments.input) if arguments.input else load_repository(Path(arguments.repository))
    diagnostics = validate_document(document)
    return CommandOutcome({"valid": not diagnostics, "diagnostics": diagnostics}, 1 if diagnostics else 0)
