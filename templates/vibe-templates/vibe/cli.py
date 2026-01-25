"""Vibe CLI - Smart project generator."""

from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table

from .config import TEMPLATES
from .generator import ProjectGenerator

app = typer.Typer(
    name="vibe",
    help="Smart project generator for vibe coding",
    no_args_is_help=True,
)
console = Console()


@app.command()
def new(
    template: Optional[str] = typer.Argument(None, help="Template to use"),
    name: Optional[str] = typer.Argument(None, help="Project name"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Override destination category"),
    docker: bool = typer.Option(False, "--docker", "-d", help="Include Docker support"),
    tests: bool = typer.Option(False, "--tests", "-t", help="Include test structure"),
    ci: bool = typer.Option(False, "--ci", help="Include GitHub Actions CI"),
):
    """Create a new project from template."""

    # Interactive mode if template not provided
    if template is None:
        template = _interactive_template_select()

    if template not in TEMPLATES:
        console.print(f"[red]Unknown template: {template}[/]")
        console.print(f"Available: {', '.join(TEMPLATES.keys())}")
        raise typer.Exit(1)

    # Interactive mode if name not provided
    if name is None:
        name = Prompt.ask("Project name")

    # Validate name
    if not name or not name.replace("-", "").replace("_", "").isalnum():
        console.print("[red]Invalid project name. Use alphanumeric characters, hyphens, or underscores.[/]")
        raise typer.Exit(1)

    # Generate project
    generator = ProjectGenerator()
    try:
        project_dir = generator.generate(
            template_name=template,
            project_name=name,
            category=category,
            docker=docker,
            tests=tests,
            ci=ci,
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)


@app.command()
def list():
    """List available templates."""
    table = Table(title="Available Templates")
    table.add_column("Template", style="cyan")
    table.add_column("Description")
    table.add_column("Destination", style="dim")
    table.add_column("Stack", style="green")

    for name, config in TEMPLATES.items():
        table.add_row(
            name,
            config.description,
            config.destination,
            ", ".join(config.stack[:3]) + ("..." if len(config.stack) > 3 else ""),
        )

    console.print(table)


def _interactive_template_select() -> str:
    """Interactive template selection."""
    console.print("\n[bold]Available templates:[/]\n")

    for i, (name, config) in enumerate(TEMPLATES.items(), 1):
        console.print(f"  [cyan]{i}[/]. [bold]{name}[/] - {config.description}")

    console.print()

    while True:
        choice = Prompt.ask("Select template", choices=[str(i) for i in range(1, len(TEMPLATES) + 1)] + list(TEMPLATES.keys()))

        if choice.isdigit():
            idx = int(choice) - 1
            return list(TEMPLATES.keys())[idx]
        elif choice in TEMPLATES:
            return choice


if __name__ == "__main__":
    app()
