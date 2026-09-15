"""Read and validate the complete native repository, including cross-file references."""

from dataclasses import dataclass
from pathlib import Path

from dal.model import validate_document
from dal.repository import semantic_files, read_document
from .model import HealthIssue


@dataclass(frozen=True)
class AuthoredDocument:
    path: Path
    relative_path: str
    value: dict[str, object]


def inspect_authored(root: Path):
    failures, gaps, documents = [], [], []
    paths = semantic_files(root)
    if not paths:
        failures.append(HealthIssue("SEMANTIC_REPOSITORY_EMPTY", "semantic",
            "No native resource files were found.", "dal init"))
    for path in paths:
        relative = path.relative_to(root).as_posix()
        try:
            document = read_document(path)
            if document.get("version") != 1 or not isinstance(document.get("objects"), list) or set(document) - {"version", "objects"}:
                raise ValueError("expected version: 1 and objects: []")
            documents.append(AuthoredDocument(path, relative, document))
        except (OSError, UnicodeError, ValueError) as error:
            failures.append(HealthIssue("FILE_CORRUPT", relative, str(error), "dal validate"))
    combined = {"version": 1, "objects": [obj for doc in documents for obj in doc.value["objects"]]}
    diagnostics = validate_document(combined)
    failures.extend(HealthIssue(issue.code, issue.pointer, issue.message, "dal validate") for issue in diagnostics)
    if not diagnostics:
        for resource in combined["objects"]:
            if resource["kind"] in {"table", "metric"} and not resource.get("grain") and resource.get("status") != "deprecated":
                gaps.append(HealthIssue("GRAIN_MISSING", resource["id"],
                    "Grain is not defined; this is a knowledge gap, not invalid data.",
                    "dal proposal create --help"))
    return failures, gaps, tuple(documents)
