"""Stable, small entry point for the existing Metso evidence agent.

No data, secrets, model logic, or routing rules live in this wrapper.
Command-line arguments are delegated to the established chat module.
"""


def main() -> None:
    from metso_agent.agent.chat import main as run_chat

    run_chat()


if __name__ == "__main__":
    main()
