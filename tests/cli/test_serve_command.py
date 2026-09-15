from dal.cli import serve_commands
from dal.cli.main import build_parser


def test_serve_exposes_server_arguments_without_loading_api_dependencies(tmp_path):
    arguments = build_parser().parse_args([
        "serve", "--repository", str(tmp_path), "--bundle", "bundle",
        "--host", "0.0.0.0", "--port", "9000", "--allow-remote",
        "--auth-token", "secret",
    ])

    assert arguments.server_bundle.name == "bundle"
    assert arguments.handler is serve_commands.run


def test_serve_delegates_to_public_server_entrypoint(tmp_path, monkeypatch):
    captured = []
    monkeypatch.setattr(serve_commands, "_server_main", lambda argv: captured.append(argv) or 0)
    arguments = build_parser().parse_args([
        "serve", "--repository", str(tmp_path), "--bundle", "bundle",
        "--host", "0.0.0.0", "--port", "9000", "--allow-remote",
        "--auth-token", "secret",
    ])

    outcome = arguments.handler(arguments)

    assert outcome.exit_code == 0
    assert captured == [[
        "--repository", str(tmp_path), "--bundle", "bundle",
        "--host", "0.0.0.0", "--port", "9000", "--allow-remote",
        "--auth-token", "secret",
    ]]
