"""One-way native import; existing authored objects are never overwritten."""

from pathlib import Path
import hashlib

from dal.documents import dump_document, canonical_json
from dal.evidence import SnapshotRepository
from dal.model import require_valid
from dal.repository import load_repository, replace_texts, repository_lock

from .contracts import CommandOutcome
from .files import read_document
from .serialization import dumps


def register(commands):
    command = commands.add_parser("import", help="Import a native JSON/YAML document or former DAL JSON graph.")
    command.add_argument("input", type=Path)
    command.add_argument("--name", default="imported")
    command.set_defaults(handler=run)


def _convert(path, name):
    from dal.legacy import CatalogImport, LegacyGraphImporter

    if path.suffix.lower() in {".zip", ".duckdb"}:
        raise ValueError("DuckDB and ZIP imports are not supported. Import a native DAL JSON/YAML document instead.")
    if path.is_file():
        value = read_document(str(path))
        if value.get("version") == 1 and isinstance(value.get("objects"), list):
            return CatalogImport(value, 0, 0, 0, ())
    return LegacyGraphImporter(path).convert(name)


def run(arguments):
    result = _convert(arguments.input, arguments.name)
    root = Path(arguments.repository)
    require_valid(result.document)
    with repository_lock(root):
        existing = load_repository(root)
        indexed = {item["id"]: item for item in existing["objects"]}
        additions = []
        for item in result.document["objects"]:
            if item["id"] in indexed and indexed[item["id"]] != item:
                raise ValueError(f"import conflicts with authored object {item['id']}; use a proposal or source refresh")
            if item["id"] not in indexed:
                additions.append(item)
        require_valid({"version": 1, "objects": existing["objects"] + additions})
        destination = root / "semantic" / "imported.yaml"
        writes = {}
        if additions:
            previous = read_document(str(destination))["objects"] if destination.exists() else []
            writes[destination] = dump_document({"version": 1, "objects": previous + additions})
        snapshot = SnapshotRepository(root / "evidence").put(result.evidence) if result.evidence else None
        identifier = hashlib.sha256(canonical_json(result.document)).hexdigest()[:24]
        report = root / ".dal" / "imports" / f"{identifier}.json"
        writes[report] = dumps({"source": str(arguments.input), "diagnostics": result.diagnostics,
                               "omitted_records": result.omitted_records}) + "\n"
        replace_texts(writes)
    return CommandOutcome({"imported_objects": len(additions), "diagnostics": result.diagnostics,
                           "evidence": snapshot, "report": report,
                           "next_commands": ["dal validate", "dal build"]})
