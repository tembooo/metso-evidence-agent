from pathlib import Path

from rich.console import Console


def main() -> None:
    console = Console()

    project_root = Path(__file__).resolve().parents[2]

    raw_data_dir = project_root / "raw" / "data"

    console.print(
        "\n[bold cyan]METSO AI SALES ASSISTANT[/bold cyan]"
    )

    console.print(
        "[green]Python environment is working.[/green]"
    )

    console.print(f"Project root: {project_root}")

    console.print(
        f"Raw data found: {raw_data_dir.is_dir()}"
    )

    if not raw_data_dir.is_dir():
        console.print(
            "[red]ERROR: Raw data directory is missing.[/red]"
        )
        raise SystemExit(1)

    console.print(
        "[bold green]Stage 00 smoke test passed![/bold green]"
    )


if __name__ == "__main__":
    main()