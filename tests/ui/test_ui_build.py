import subprocess
from pathlib import Path

from tests.api.helpers import api_client

ROOT = Path(__file__).parents[2]
WEB = ROOT / "web"
STATIC = ROOT / "dal" / "api" / "static"


def test_dependency_free_ui_build_produces_packaged_assets():
    subprocess.run(["npm", "run", "build", "--prefix", str(WEB)], check=True)

    assert (STATIC / "index.html").is_file()
    assert (STATIC / "assets" / "app.js").is_file()
    assert (STATIC / "assets" / "views" / "search.js").is_file()


def test_visual_contract_uses_ledger_palette_and_responsive_accessibility():
    html = (WEB / "src" / "index.html").read_text(encoding="utf-8")
    css = (WEB / "src" / "styles.css").read_text(encoding="utf-8").lower()

    for label in ("Search", "Catalog", "Ontology", "Curation", "Doctrine", "Gold queries", "Health"):
        assert f">{label}" in html
    for color in ("#172129", "#f7f8f4", "#18735a", "#d68a22", "#b94040", "#d7ddd8"):
        assert color in css
    assert "linear-gradient" not in css
    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css
    assert "@media (max-width: 680px)" in css


def test_server_supports_ui_deep_links_and_static_assets(tmp_path):
    client = api_client(tmp_path)

    deep_link = client.get("/gold-queries")
    asset = client.get("/assets/views/search.js")
    missing_api = client.get("/api/v1/not-real")

    assert deep_link.status_code == 200
    assert "DAL context ledger" in deep_link.text
    assert asset.status_code == 200
    assert "Context trail" in asset.text
    assert missing_api.status_code == 404
    assert missing_api.headers["content-type"].startswith("application/json")
    assert client.get("/ontology?kind=entity").status_code == 200
    for asset_name in ("views/resource.js", "views/proposal.js", "lib/format.js", "lib/resources.js"):
        assert client.get(f"/assets/{asset_name}").status_code == 200
