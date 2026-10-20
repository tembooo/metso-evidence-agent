from metso_agent.cli import main


def test_cli_entrypoint_exists():
    assert callable(main)