from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from .helpers import api_client


def test_parallel_catalog_panels_return_json(tmp_path):
    client = api_client(tmp_path)
    paths = [
        "/api/v1/resources/table",
        "/api/v1/graph/neighbors?object_id=urn:dal:table:orders",
        "/api/v1/graph/evidence?object_id=urn:dal:table:orders",
        "/api/v1/graph/connections?object_id=urn:dal:table:orders",
        "/api/v1/health",
        "/api/v1/revisions",
    ]
    barrier = Barrier(len(paths))

    def fetch(path):
        barrier.wait(timeout=10)
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert isinstance(response.json(), dict)

    with ThreadPoolExecutor(max_workers=len(paths)) as pool:
        for _ in range(3):
            list(pool.map(fetch, paths))
