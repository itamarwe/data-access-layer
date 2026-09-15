from pathlib import Path

from fastapi.testclient import TestClient

from dal.api import ServerConfig, create_app
from dal.compiler import BundleBuilder
from dal.documents import dump_document
from tests.application.fixtures import native_document


def api_client(root: Path, *, host: str = "127.0.0.1", token: str | None = None) -> TestClient:
    document = native_document()
    semantic = root / "semantic" / "sales.yaml"
    semantic.parent.mkdir(parents=True, exist_ok=True)
    semantic.write_text(dump_document(document), encoding="utf-8")
    bundle = root / ".dal" / "query"
    BundleBuilder(bundle).build(document)
    config = ServerConfig(root, bundle, host=host, allow_remote=host != "127.0.0.1", auth_token=token)
    return TestClient(create_app(config))
