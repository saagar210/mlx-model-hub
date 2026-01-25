"""Core project generation logic."""

import os
import shutil
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from rich.console import Console

from .config import TEMPLATES, TemplateConfig, get_claude_code_root, get_template_dir

console = Console()


class ProjectGenerator:
    """Generates projects from templates."""

    def __init__(self):
        self.template_dir = get_template_dir()
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            keep_trailing_newline=True,
        )

    def generate(
        self,
        template_name: str,
        project_name: str,
        category: str | None = None,
        docker: bool = False,
        tests: bool = False,
        ci: bool = False,
    ) -> Path:
        """Generate a new project from template."""
        if template_name not in TEMPLATES:
            raise ValueError(f"Unknown template: {template_name}")

        config = TEMPLATES[template_name]

        # Determine destination
        dest_category = category or config.destination
        project_dir = get_claude_code_root() / dest_category / project_name

        if project_dir.exists():
            raise ValueError(f"Project already exists: {project_dir}")

        console.print(f"[bold blue]Creating {template_name} project:[/] {project_name}")
        console.print(f"[dim]Location: {project_dir}[/]")

        # Create project directory
        project_dir.mkdir(parents=True, exist_ok=True)

        # Context for templates
        context = {
            "project_name": project_name,
            "project_slug": project_name.replace("-", "_").replace(" ", "_").lower(),
            "template_name": template_name,
            "stack": config.stack,
            "docker": docker,
            "tests": tests,
            "ci": ci,
        }

        # Generate base files (CLAUDE.md, .gitignore)
        self._generate_base_files(project_dir, context)

        # Generate template-specific files
        if template_name == "fullstack":
            self._generate_fullstack(project_dir, context)
        else:
            self._generate_template_files(template_name, project_dir, context)

        # Generate optional features
        if docker and "docker" in config.optional_features:
            self._generate_docker(template_name, project_dir, context)
        if tests and "tests" in config.optional_features:
            self._generate_tests(template_name, project_dir, context)
        if ci and "ci" in config.optional_features:
            self._generate_ci(project_dir, context)

        # Generate Claude commands
        self._generate_commands(template_name, project_dir, context)

        # Initialize git
        self._init_git(project_dir)

        # Initialize Task Master
        self._init_taskmaster(project_dir, context)

        console.print(f"\n[bold green]Project created successfully![/]")
        console.print(f"\n[bold]Next steps:[/]")
        console.print(f"  cd {project_dir}")
        console.print(f"  claude  # Start coding!")

        return project_dir

    def _generate_base_files(self, project_dir: Path, context: dict):
        """Generate base files common to all templates."""
        console.print("  [dim]Creating CLAUDE.md...[/]")

        # CLAUDE.md
        template = self.env.get_template("base/CLAUDE.md.j2")
        content = template.render(**context)
        (project_dir / "CLAUDE.md").write_text(content)

        # .gitignore
        template = self.env.get_template("base/.gitignore.j2")
        content = template.render(**context)
        (project_dir / ".gitignore").write_text(content)

    def _generate_template_files(self, template_name: str, project_dir: Path, context: dict):
        """Generate template-specific files."""
        console.print(f"  [dim]Creating {template_name} structure...[/]")

        template_path = self.template_dir / template_name
        if not template_path.exists():
            console.print(f"  [yellow]Template directory not found, using minimal setup[/]")
            return

        # Walk template directory and render each file
        for root, dirs, files in os.walk(template_path):
            rel_root = Path(root).relative_to(template_path)

            for file in files:
                if file.endswith(".j2"):
                    # Render Jinja template
                    template_rel_path = f"{template_name}/{rel_root}/{file}"
                    template = self.env.get_template(template_rel_path)
                    content = template.render(**context)

                    # Remove .j2 extension and create file
                    output_name = file[:-3]  # Remove .j2
                    output_path = project_dir / rel_root / output_name
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text(content)
                else:
                    # Copy file as-is
                    src = Path(root) / file
                    dst = project_dir / rel_root / file
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)

    def _generate_fullstack(self, project_dir: Path, context: dict):
        """Generate fullstack project with backend and frontend."""
        console.print("  [dim]Creating fullstack structure...[/]")

        # Create backend (python-api)
        backend_dir = project_dir / "backend"
        backend_dir.mkdir(exist_ok=True)
        backend_context = {**context, "template_name": "python-api"}
        self._generate_template_files("python-api", backend_dir, backend_context)

        # Create frontend (nextjs)
        frontend_dir = project_dir / "frontend"
        frontend_dir.mkdir(exist_ok=True)
        frontend_context = {**context, "template_name": "nextjs"}
        self._generate_template_files("nextjs", frontend_dir, frontend_context)

        # Generate fullstack-specific files (docker-compose)
        self._generate_template_files("fullstack", project_dir, context)

    def _generate_docker(self, template_name: str, project_dir: Path, context: dict):
        """Generate Docker files."""
        console.print("  [dim]Adding Docker support...[/]")

        try:
            template = self.env.get_template(f"{template_name}/Dockerfile.j2")
            content = template.render(**context)
            (project_dir / "Dockerfile").write_text(content)
        except Exception:
            # Use base Dockerfile template
            dockerfile = f"""FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install -e .

CMD ["uvicorn", "{context['project_slug']}.main:app", "--host", "0.0.0.0", "--port", "8000"]
"""
            (project_dir / "Dockerfile").write_text(dockerfile)

    def _generate_tests(self, template_name: str, project_dir: Path, context: dict):
        """Generate test structure."""
        console.print("  [dim]Adding tests structure...[/]")

        tests_dir = project_dir / "tests"
        tests_dir.mkdir(exist_ok=True)

        (tests_dir / "__init__.py").write_text("")
        (tests_dir / "test_example.py").write_text(f'''"""Example test file."""

def test_example():
    """Example test that passes."""
    assert True
''')

    def _generate_ci(self, project_dir: Path, context: dict):
        """Generate GitHub Actions workflow."""
        console.print("  [dim]Adding CI workflow...[/]")

        workflows_dir = project_dir / ".github" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)

        workflow = """name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[test]"
      - run: pytest
"""
        (workflows_dir / "ci.yml").write_text(workflow)

    def _generate_commands(self, template_name: str, project_dir: Path, context: dict):
        """Generate Claude commands for the project."""
        console.print("  [dim]Creating Claude commands...[/]")

        commands_dir = project_dir / ".claude" / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)

        config = TEMPLATES[template_name]

        # Generate commands based on template
        if "run" in config.commands:
            if template_name in ("python-api", "python-ml"):
                (commands_dir / "run.md").write_text(
                    f"Run the development server:\n\n```bash\ncd {project_dir}\nuv run python -m {context['project_slug']}.main\n```"
                )
            elif template_name == "nextjs":
                (commands_dir / "run.md").write_text(
                    f"Run the development server:\n\n```bash\ncd {project_dir}\nnpm run dev\n```"
                )

        if "dev" in config.commands and template_name == "fullstack":
            (commands_dir / "dev.md").write_text(
                "Start both backend and frontend:\n\n```bash\n# Terminal 1: Backend\ncd backend && uv run python -m src.main\n\n# Terminal 2: Frontend\ncd frontend && npm run dev\n```"
            )

    def _init_git(self, project_dir: Path):
        """Initialize git repository."""
        console.print("  [dim]Initializing git...[/]")

        subprocess.run(
            ["git", "init"],
            cwd=project_dir,
            capture_output=True,
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=project_dir,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit from vibe templates"],
            cwd=project_dir,
            capture_output=True,
        )

    def _init_taskmaster(self, project_dir: Path, context: dict):
        """Initialize Task Master."""
        console.print("  [dim]Initializing Task Master...[/]")

        taskmaster_dir = project_dir / ".taskmaster"
        taskmaster_dir.mkdir(exist_ok=True)

        # Create minimal taskmaster config
        config = {
            "projectName": context["project_name"],
            "version": "1.0.0",
        }

        import json
        (taskmaster_dir / "config.json").write_text(json.dumps(config, indent=2))

        # Create tasks directory
        (taskmaster_dir / "tasks").mkdir(exist_ok=True)
        (taskmaster_dir / "docs").mkdir(exist_ok=True)
