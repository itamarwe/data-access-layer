import pytest

from dal.api import ServerConfig

from .helpers import api_client


def test_loopback_is_the_default(tmp_path):
    config = ServerConfig(tmp_path, tmp_path / "bundle")

    assert config.host == "127.0.0.1"
    assert config.allow_remote is False


def test_non_loopback_requires_opt_in_and_authentication(tmp_path):
    with pytest.raises(ValueError, match="allow-remote"):
        ServerConfig(tmp_path, tmp_path / "bundle", host="0.0.0.0")
    with pytest.raises(ValueError, match="authentication token"):
        ServerConfig(tmp_path, tmp_path / "bundle", host="0.0.0.0", allow_remote=True)


def test_configured_auth_protects_every_api_route(tmp_path):
    client = api_client(tmp_path, host="0.0.0.0", token="secret")

    assert client.get("/api/v1/revisions").status_code == 401
    assert client.get("/api/v1/openapi.json").status_code == 401
    assert client.get(
        "/api/v1/revisions", headers={"Authorization": "Bearer wrong"},
    ).status_code == 403
    assert client.get(
        "/api/v1/revisions", headers={"Authorization": "Bearer secret"},
    ).status_code == 200
