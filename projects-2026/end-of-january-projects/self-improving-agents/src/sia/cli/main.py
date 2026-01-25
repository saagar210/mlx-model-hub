"""
SIA CLI - Command Line Interface

Main entry point for the SIA framework CLI.
"""

import asyncio
from typing import Annotated, Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from sia import __version__
from sia.config import get_config

app = typer.Typer(
    name="sia",
    help="Self-Improving Agents Framework CLI",
    no_args_is_help=True,
)

console = Console()

# Verbose flag
verbose_option = Annotated[
    bool,
    typer.Option("--verbose", "-v", help="Enable verbose output"),
]


def version_callback(value: bool) -> None:
    if value:
        rprint(f"[bold blue]SIA[/bold blue] version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-V",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit",
        ),
    ] = None,
) -> None:
    """Self-Improving Agents Framework - Build agents that improve themselves."""
    pass


# ============================================================================
# Database Commands
# ============================================================================

db_app = typer.Typer(help="Database management commands")
app.add_typer(db_app, name="db")


@db_app.command("init")
def db_init(verbose: verbose_option = False) -> None:
    """Initialize the database schema."""
    from sia.db import init_db

    async def _init() -> None:
        config = get_config()
        if verbose:
            rprint(f"[dim]Connecting to: {config.database.url}[/dim]")

        try:
            db = await init_db(config)
            health = await db.health_check()

            if health["status"] == "healthy":
                rprint("[green]✓[/green] Database initialized successfully")
                if verbose:
                    rprint(f"[dim]  Version: {health['version']}[/dim]")
                    rprint(f"[dim]  Extensions: {', '.join(health['extensions'])}[/dim]")
                    rprint(f"[dim]  Tables: {len(health['tables'])} tables[/dim]")
            else:
                rprint(f"[red]✗[/red] Database initialization failed: {health.get('error')}")
                raise typer.Exit(1)
        finally:
            from sia.db.connection import close_db
            await close_db()

    asyncio.run(_init())


@db_app.command("health")
def db_health(verbose: verbose_option = False) -> None:
    """Check database health status."""
    from sia.db import init_db

    async def _health() -> None:
        try:
            db = await init_db()
            health = await db.health_check()

            if health["status"] == "healthy":
                rprint("[green]✓[/green] Database is healthy")

                if verbose:
                    # Version
                    rprint(f"\n[bold]PostgreSQL Version:[/bold]")
                    rprint(f"  {health['version']}")

                    # Extensions
                    rprint(f"\n[bold]Extensions:[/bold]")
                    for ext in health["extensions"]:
                        rprint(f"  [green]✓[/green] {ext}")

                    # Tables
                    rprint(f"\n[bold]Tables ({len(health['tables'])}):[/bold]")
                    for table in health["tables"]:
                        rprint(f"  • {table}")

                    # Pool stats
                    pool = health["pool"]
                    rprint(f"\n[bold]Connection Pool:[/bold]")
                    rprint(f"  Size: {pool['size']} (min: {pool['min']}, max: {pool['max']})")
                    rprint(f"  Free: {pool['free']}")
            else:
                rprint(f"[red]✗[/red] Database is unhealthy")
                rprint(f"  Error: {health.get('error')}")
                raise typer.Exit(1)
        finally:
            from sia.db.connection import close_db
            await close_db()

    asyncio.run(_health())


@db_app.command("stats")
def db_stats() -> None:
    """Show database statistics."""
    from sia.db import init_db

    async def _stats() -> None:
        try:
            db = await init_db()

            # Get counts from each table
            tables = ["agents", "executions", "skills", "episodic_memory", "semantic_memory"]
            stats = {}

            for table in tables:
                count = await db.fetchval(f"SELECT COUNT(*) FROM {table}")
                stats[table] = count

            # Display as table
            table = Table(title="Database Statistics")
            table.add_column("Table", style="cyan")
            table.add_column("Count", justify="right", style="green")

            for name, count in stats.items():
                table.add_row(name, str(count))

            console.print(table)
        finally:
            from sia.db.connection import close_db
            await close_db()

    asyncio.run(_stats())


# ============================================================================
# Agent Commands
# ============================================================================

agent_app = typer.Typer(help="Agent management commands")
app.add_typer(agent_app, name="agent")


@agent_app.command("list")
def agent_list(
    status: Annotated[
        Optional[str],
        typer.Option("--status", "-s", help="Filter by status (active, testing, retired)"),
    ] = None,
    verbose: verbose_option = False,
) -> None:
    """List all registered agents."""
    from sia.db import init_db

    async def _list() -> None:
        try:
            db = await init_db()

            query = """
                SELECT id, name, version, type, status, success_rate,
                       total_executions, created_at
                FROM agents
                WHERE retired_at IS NULL
            """
            params = []

            if status:
                query += " AND status = $1"
                params.append(status)

            query += " ORDER BY name, version DESC"

            rows = await db.fetch(query, *params)

            if not rows:
                rprint("[yellow]No agents found[/yellow]")
                return

            table = Table(title="Registered Agents")
            table.add_column("Name", style="cyan")
            table.add_column("Version", style="dim")
            table.add_column("Type")
            table.add_column("Status")
            table.add_column("Success Rate", justify="right")
            table.add_column("Executions", justify="right")

            for row in rows:
                success_rate = f"{row['success_rate']:.1%}" if row['success_rate'] else "N/A"
                status_style = {
                    "active": "green",
                    "testing": "yellow",
                    "retired": "dim",
                    "failed": "red",
                }.get(row["status"], "")

                table.add_row(
                    row["name"],
                    row["version"],
                    row["type"],
                    f"[{status_style}]{row['status']}[/{status_style}]",
                    success_rate,
                    str(row["total_executions"]),
                )

            console.print(table)
        finally:
            from sia.db.connection import close_db
            await close_db()

    asyncio.run(_list())


@agent_app.command("run")
def agent_run(
    agent_name: Annotated[str, typer.Argument(help="Name of the agent to run")],
    task: Annotated[str, typer.Argument(help="Task description")],
    verbose: verbose_option = False,
) -> None:
    """Run an agent with a task."""
    rprint(f"[yellow]Running agent '{agent_name}' with task:[/yellow]")
    rprint(f"  {task}")
    rprint("\n[dim]Agent execution not yet implemented (Phase 9)[/dim]")


@agent_app.command("stats")
def agent_stats(
    agent_name: Annotated[str, typer.Argument(help="Name of the agent")],
) -> None:
    """Show statistics for an agent."""
    from sia.db import init_db

    async def _stats() -> None:
        try:
            db = await init_db()

            row = await db.fetchrow(
                """
                SELECT name, version, type, status, success_rate,
                       total_executions, successful_executions,
                       avg_execution_time_ms, avg_tokens_used,
                       created_at, last_execution
                FROM agents
                WHERE name = $1 AND retired_at IS NULL
                ORDER BY version DESC
                LIMIT 1
                """,
                agent_name,
            )

            if not row:
                rprint(f"[red]Agent '{agent_name}' not found[/red]")
                raise typer.Exit(1)

            rprint(f"\n[bold cyan]{row['name']}[/bold cyan] v{row['version']}")
            rprint(f"  Type: {row['type']}")
            rprint(f"  Status: {row['status']}")
            rprint(f"\n[bold]Performance:[/bold]")
            rprint(f"  Success Rate: {row['success_rate']:.1%}" if row['success_rate'] else "  Success Rate: N/A")
            rprint(f"  Total Executions: {row['total_executions']}")
            rprint(f"  Successful: {row['successful_executions']}")
            if row['avg_execution_time_ms']:
                rprint(f"  Avg Time: {row['avg_execution_time_ms']:.0f}ms")
            if row['avg_tokens_used']:
                rprint(f"  Avg Tokens: {row['avg_tokens_used']:.0f}")
            rprint(f"\n[bold]Timeline:[/bold]")
            rprint(f"  Created: {row['created_at']}")
            if row['last_execution']:
                rprint(f"  Last Run: {row['last_execution']}")
        finally:
            from sia.db.connection import close_db
            await close_db()

    asyncio.run(_stats())


# ============================================================================
# Skill Commands
# ============================================================================

skill_app = typer.Typer(help="Skill management commands")
app.add_typer(skill_app, name="skill")


@skill_app.command("list")
def skill_list(
    category: Annotated[
        Optional[str],
        typer.Option("--category", "-c", help="Filter by category"),
    ] = None,
    status: Annotated[
        Optional[str],
        typer.Option("--status", "-s", help="Filter by status"),
    ] = None,
) -> None:
    """List all skills."""
    from sia.db import init_db

    async def _list() -> None:
        try:
            db = await init_db()

            query = "SELECT id, name, category, status, success_rate, usage_count FROM skills WHERE 1=1"
            params = []
            param_idx = 1

            if category:
                query += f" AND category = ${param_idx}"
                params.append(category)
                param_idx += 1

            if status:
                query += f" AND status = ${param_idx}"
                params.append(status)

            query += " ORDER BY usage_count DESC, name"

            rows = await db.fetch(query, *params)

            if not rows:
                rprint("[yellow]No skills found[/yellow]")
                return

            table = Table(title="Skills Library")
            table.add_column("Name", style="cyan")
            table.add_column("Category")
            table.add_column("Status")
            table.add_column("Success Rate", justify="right")
            table.add_column("Uses", justify="right")

            for row in rows:
                success_rate = f"{row['success_rate']:.1%}" if row['success_rate'] else "N/A"
                table.add_row(
                    row["name"],
                    row["category"],
                    row["status"],
                    success_rate,
                    str(row["usage_count"]),
                )

            console.print(table)
        finally:
            from sia.db.connection import close_db
            await close_db()

    asyncio.run(_list())


@skill_app.command("search")
def skill_search(
    query: Annotated[str, typer.Argument(help="Search query")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 10,
    category: Annotated[Optional[str], typer.Option("--category", "-c", help="Filter by category")] = None,
    no_rerank: Annotated[bool, typer.Option("--no-rerank", help="Disable reranking")] = False,
    verbose: verbose_option = False,
) -> None:
    """Search skills by description."""
    from sia.db import init_db
    from sia.skills import SkillRetriever

    async def _search() -> None:
        try:
            db = await init_db()
            async with db.session() as session:
                retriever = SkillRetriever(session=session)

                results = await retriever.search(
                    query=query,
                    limit=limit,
                    category=category,
                    rerank=not no_rerank,
                )

                if not results:
                    rprint("[yellow]No skills found[/yellow]")
                    return

                table = Table(title=f"Skill Search: '{query}'")
                table.add_column("Name", style="cyan")
                table.add_column("Category")
                table.add_column("Description", width=40)
                table.add_column("Score", justify="right")
                table.add_column("Success", justify="right")

                for result in results:
                    desc = result.skill.description
                    if len(desc) > 40:
                        desc = desc[:37] + "..."
                    table.add_row(
                        result.skill.name,
                        result.skill.category or "N/A",
                        desc,
                        f"{result.combined_score:.3f}",
                        f"{result.success_score:.0%}" if result.success_score else "N/A",
                    )

                console.print(table)

                if verbose:
                    rprint(f"\n[dim]Retrieved {len(results)} skills[/dim]")

                await retriever.close()
        finally:
            from sia.db.connection import close_db
            await close_db()

    asyncio.run(_search())


@skill_app.command("show")
def skill_show(
    name: Annotated[str, typer.Argument(help="Skill name")],
) -> None:
    """Show details of a skill."""
    from sia.db import init_db

    async def _show() -> None:
        try:
            db = await init_db()

            row = await db.fetchrow(
                """
                SELECT name, description, category, subcategory, status,
                       success_rate, usage_count, signature, code,
                       tags, python_dependencies, created_at, last_used
                FROM skills WHERE name = $1
                """,
                name,
            )

            if not row:
                rprint(f"[red]Skill '{name}' not found[/red]")
                raise typer.Exit(1)

            rprint(f"\n[bold cyan]{row['name']}[/bold cyan]")
            rprint(f"  {row['description']}")
            rprint(f"\n[bold]Metadata:[/bold]")
            rprint(f"  Category: {row['category']}")
            if row['subcategory']:
                rprint(f"  Subcategory: {row['subcategory']}")
            rprint(f"  Status: {row['status']}")
            if row['tags']:
                rprint(f"  Tags: {', '.join(row['tags'])}")
            rprint(f"\n[bold]Performance:[/bold]")
            if row['success_rate']:
                rprint(f"  Success Rate: {row['success_rate']:.0%}")
            rprint(f"  Usage Count: {row['usage_count']}")
            if row['signature']:
                rprint(f"\n[bold]Signature:[/bold]")
                rprint(f"  {row['signature']}")
            if row['python_dependencies']:
                rprint(f"\n[bold]Dependencies:[/bold]")
                for dep in row['python_dependencies']:
                    rprint(f"  - {dep}")
        finally:
            from sia.db.connection import close_db
            await close_db()

    asyncio.run(_show())


@skill_app.command("validate")
def skill_validate(
    name: Annotated[str, typer.Argument(help="Skill name to validate")],
) -> None:
    """Validate a skill's code."""
    from sia.db import init_db
    from sia.skills import SkillValidator

    async def _validate() -> None:
        try:
            db = await init_db()

            row = await db.fetchrow(
                "SELECT name, code FROM skills WHERE name = $1",
                name,
            )

            if not row:
                rprint(f"[red]Skill '{name}' not found[/red]")
                raise typer.Exit(1)

            if not row['code']:
                rprint(f"[yellow]Skill '{name}' has no code to validate[/yellow]")
                return

            validator = SkillValidator()
            result = validator.validate(row['code'])

            if result.is_valid:
                rprint(f"[green]✓[/green] Skill '{name}' is valid")
            else:
                rprint(f"[red]✗[/red] Skill '{name}' has errors:")
                for error in result.errors:
                    rprint(f"  - {error}")

            if result.warnings:
                rprint(f"\n[yellow]Warnings:[/yellow]")
                for warning in result.warnings:
                    rprint(f"  - {warning}")

            # Security report
            report = validator.get_security_report(row['code'])
            rprint(f"\n[bold]Security:[/bold] {report['risk_level'].upper()}")
            if report['dangerous_patterns']:
                for pattern in report['dangerous_patterns']:
                    rprint(f"  [red]- {pattern}[/red]")

        finally:
            from sia.db.connection import close_db
            await close_db()

    asyncio.run(_validate())


# ============================================================================
# Memory Commands
# ============================================================================

memory_app = typer.Typer(help="Memory system commands")
app.add_typer(memory_app, name="memory")


@memory_app.command("search")
def memory_search(
    query: Annotated[str, typer.Argument(help="Search query")],
    memory_type: Annotated[
        Optional[str],
        typer.Option("--type", "-t", help="Memory type (episodic, semantic, procedural, all)"),
    ] = "all",
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 10,
    no_rerank: Annotated[bool, typer.Option("--no-rerank", help="Disable reranking")] = False,
    verbose: verbose_option = False,
) -> None:
    """Search across memory systems."""
    from sia.db import init_db
    from sia.memory import UnifiedMemoryManager

    async def _search() -> None:
        try:
            db = await init_db()
            async with db.session() as session:
                manager = UnifiedMemoryManager(session=session)

                include_episodic = memory_type in ("all", "episodic")
                include_semantic = memory_type in ("all", "semantic")
                include_procedural = memory_type in ("all", "procedural")

                if verbose:
                    rprint(f"[dim]Searching: episodic={include_episodic}, semantic={include_semantic}, procedural={include_procedural}[/dim]")

                results = await manager.search(
                    query=query,
                    limit=limit,
                    include_episodic=include_episodic,
                    include_semantic=include_semantic,
                    include_procedural=include_procedural,
                    rerank=not no_rerank,
                )

                if not results.items:
                    rprint("[yellow]No results found[/yellow]")
                    return

                table = Table(title=f"Memory Search: '{query}'")
                table.add_column("Type", style="cyan", width=10)
                table.add_column("Content", width=50)
                table.add_column("Score", justify="right", width=8)

                for item in results.items:
                    content = item.content[:80] + "..." if len(item.content) > 80 else item.content
                    type_style = {
                        "episodic": "blue",
                        "semantic": "green",
                        "procedural": "magenta",
                    }.get(item.memory_type, "")
                    table.add_row(
                        f"[{type_style}]{item.memory_type}[/{type_style}]",
                        content,
                        f"{item.score:.3f}",
                    )

                console.print(table)

                if verbose:
                    rprint(f"\n[dim]Retrieved: {results.total_retrieved} | Returned: {len(results.items)} | Reranked: {results.reranked}[/dim]")

                await manager.close()
        finally:
            from sia.db.connection import close_db
            await close_db()

    asyncio.run(_search())


@memory_app.command("stats")
def memory_stats(verbose: verbose_option = False) -> None:
    """Show memory system statistics."""
    from sia.db import init_db

    async def _stats() -> None:
        try:
            db = await init_db()

            episodic_count = await db.fetchval("SELECT COUNT(*) FROM episodic_memory")
            semantic_count = await db.fetchval("SELECT COUNT(*) FROM semantic_memory WHERE deleted_at IS NULL")
            skill_count = await db.fetchval("SELECT COUNT(*) FROM skills WHERE status = 'active'")

            rprint("\n[bold]Memory Statistics[/bold]")
            rprint(f"  Episodic memories: {episodic_count}")
            rprint(f"  Semantic facts: {semantic_count}")
            rprint(f"  Active skills: {skill_count}")
            rprint(f"  [bold]Total:[/bold] {episodic_count + semantic_count + skill_count}")

            if verbose:
                # Show additional breakdown
                semantic_by_type = await db.fetch(
                    "SELECT fact_type, COUNT(*) as count FROM semantic_memory WHERE deleted_at IS NULL GROUP BY fact_type ORDER BY count DESC"
                )
                if semantic_by_type:
                    rprint("\n[bold]Semantic by Type:[/bold]")
                    for row in semantic_by_type:
                        rprint(f"  {row['fact_type']}: {row['count']}")

                skill_by_category = await db.fetch(
                    "SELECT category, COUNT(*) as count FROM skills WHERE status = 'active' GROUP BY category ORDER BY count DESC"
                )
                if skill_by_category:
                    rprint("\n[bold]Skills by Category:[/bold]")
                    for row in skill_by_category:
                        rprint(f"  {row['category']}: {row['count']}")
        finally:
            from sia.db.connection import close_db
            await close_db()

    asyncio.run(_stats())


@memory_app.command("add-fact")
def memory_add_fact(
    fact: Annotated[str, typer.Argument(help="The fact to store")],
    fact_type: Annotated[str, typer.Option("--type", "-t", help="Fact type (rule, pattern, constraint, etc.)")] = "learned",
    category: Annotated[Optional[str], typer.Option("--category", "-c", help="Category")] = None,
    confidence: Annotated[float, typer.Option("--confidence", help="Confidence score (0-1)")] = 1.0,
    verbose: verbose_option = False,
) -> None:
    """Add a fact to semantic memory."""
    from sia.db import init_db
    from sia.memory import SemanticMemoryManager

    async def _add() -> None:
        try:
            db = await init_db()
            async with db.session() as session:
                manager = SemanticMemoryManager(session=session)

                memory = await manager.store_fact(
                    fact=fact,
                    fact_type=fact_type,
                    category=category,
                    confidence=confidence,
                    source="user",
                    source_description="Added via CLI",
                )

                await session.commit()

                rprint(f"[green]✓[/green] Fact stored successfully")
                if verbose:
                    rprint(f"  ID: {memory.id}")
                    rprint(f"  Type: {memory.fact_type}")
                    rprint(f"  Confidence: {memory.confidence}")

                await manager.close()
        finally:
            from sia.db.connection import close_db
            await close_db()

    asyncio.run(_add())


@memory_app.command("clear")
def memory_clear(
    memory_type: Annotated[str, typer.Argument(help="Memory type to clear (episodic, semantic, all)")],
    confirm: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Clear memories (use with caution!)."""
    if memory_type not in ("episodic", "semantic", "all"):
        rprint(f"[red]Invalid memory type: {memory_type}[/red]")
        rprint("Valid types: episodic, semantic, all")
        raise typer.Exit(1)

    if not confirm:
        confirm = typer.confirm(f"Are you sure you want to clear {memory_type} memory?")
        if not confirm:
            rprint("[yellow]Cancelled[/yellow]")
            return

    from sia.db import init_db

    async def _clear() -> None:
        try:
            db = await init_db()

            if memory_type in ("episodic", "all"):
                count = await db.fetchval("SELECT COUNT(*) FROM episodic_memory")
                await db.execute("DELETE FROM episodic_memory")
                rprint(f"[green]✓[/green] Cleared {count} episodic memories")

            if memory_type in ("semantic", "all"):
                count = await db.fetchval("SELECT COUNT(*) FROM semantic_memory WHERE deleted_at IS NULL")
                await db.execute("UPDATE semantic_memory SET deleted_at = NOW() WHERE deleted_at IS NULL")
                rprint(f"[green]✓[/green] Soft-deleted {count} semantic facts")

        finally:
            from sia.db.connection import close_db
            await close_db()

    asyncio.run(_clear())


# ============================================================================
# Optimization Commands
# ============================================================================

optimize_app = typer.Typer(help="DSPy optimization commands")
app.add_typer(optimize_app, name="optimize")


@optimize_app.command("run")
def optimize_run(
    agent_name: Annotated[str, typer.Argument(help="Agent to optimize")],
    optimizer: Annotated[
        str,
        typer.Option("--optimizer", "-o", help="Optimizer type (miprov2, simba)"),
    ] = "miprov2",
    trials: Annotated[
        Optional[int],
        typer.Option("--trials", "-t", help="Number of optimization trials"),
    ] = None,
    min_examples: Annotated[
        int,
        typer.Option("--min-examples", help="Minimum training examples required"),
    ] = 20,
    verbose: verbose_option = False,
) -> None:
    """Run prompt optimization for an agent."""
    from sia.db import init_db
    from sia.optimization import OptimizationRunner

    config = get_config()
    trials = trials or config.dspy.trials

    async def _optimize() -> None:
        try:
            db = await init_db()
            async with db.session() as session:
                runner = OptimizationRunner(session=session)

                rprint(f"[yellow]Starting {optimizer} optimization for '{agent_name}'[/yellow]")
                rprint(f"  Optimizer: {optimizer}")
                rprint(f"  Max trials: {trials}")
                rprint(f"  Min examples: {min_examples}")
                rprint()

                opt_config = {"num_trials": trials} if optimizer == "miprov2" else {"num_iterations": trials}

                run = await runner.run_optimization(
                    agent_name=agent_name,
                    optimizer_type=optimizer,
                    min_examples=min_examples,
                    config=opt_config,
                )

                if run.status == "completed":
                    rprint(f"[green]✓[/green] Optimization completed!")
                    rprint(f"\n[bold]Results:[/bold]")
                    rprint(f"  Baseline score: {run.baseline_score:.4f}")
                    rprint(f"  Optimized score: {run.optimized_score:.4f}")
                    rprint(f"  Improvement: {run.improvement:+.4f} ({run.improvement_pct:+.1%})")
                    rprint(f"\n  Run ID: {run.id}")

                    if verbose:
                        rprint(f"  Module path: {run.optimized_module_path}")
                        rprint(f"  Result path: {run.result_path}")
                elif run.status == "failed":
                    rprint(f"[red]✗[/red] Optimization failed")
                    rprint(f"  Error: {run.error}")
                else:
                    rprint(f"[yellow]Status: {run.status}[/yellow]")

        finally:
            from sia.db.connection import close_db
            await close_db()

    asyncio.run(_optimize())


@optimize_app.command("status")
def optimize_status(
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of runs to show")] = 10,
) -> None:
    """Show status of recent optimization runs."""
    from sia.optimization import OptimizationRunner
    from sia.db import init_db

    async def _status() -> None:
        try:
            db = await init_db()
            async with db.session() as session:
                runner = OptimizationRunner(session=session)
                runs = runner.get_recent_runs(limit=limit)

                if not runs:
                    rprint("[yellow]No optimization runs found[/yellow]")
                    return

                table = Table(title="Recent Optimization Runs")
                table.add_column("ID", style="dim", width=8)
                table.add_column("Agent", style="cyan")
                table.add_column("Optimizer")
                table.add_column("Status")
                table.add_column("Improvement", justify="right")
                table.add_column("Created")

                for run in runs:
                    status_style = {
                        "pending": "yellow",
                        "running": "blue",
                        "completed": "green",
                        "failed": "red",
                        "deployed": "magenta",
                    }.get(run.status, "")

                    improvement = f"{run.improvement_pct:+.1%}" if run.improvement_pct else "N/A"

                    table.add_row(
                        str(run.id)[:8],
                        run.agent_name,
                        run.optimizer_type,
                        f"[{status_style}]{run.status}[/{status_style}]",
                        improvement,
                        run.created_at.strftime("%Y-%m-%d %H:%M"),
                    )

                console.print(table)
        finally:
            from sia.db.connection import close_db
            await close_db()

    asyncio.run(_status())


@optimize_app.command("history")
def optimize_history(
    agent_name: Annotated[str, typer.Argument(help="Agent name")],
    verbose: verbose_option = False,
) -> None:
    """Show optimization history for an agent."""
    from sia.optimization import OptimizationRunner
    from sia.db import init_db

    async def _history() -> None:
        try:
            db = await init_db()
            async with db.session() as session:
                runner = OptimizationRunner(session=session)
                runs = runner.get_runs_for_agent(agent_name)

                if not runs:
                    rprint(f"[yellow]No optimization runs found for '{agent_name}'[/yellow]")
                    return

                rprint(f"\n[bold]Optimization History: {agent_name}[/bold]\n")

                for run in sorted(runs, key=lambda r: r.created_at, reverse=True):
                    status_style = {
                        "completed": "green",
                        "failed": "red",
                        "deployed": "magenta",
                    }.get(run.status, "yellow")

                    rprint(f"[{status_style}]● {run.status.upper()}[/{status_style}] - {run.created_at.strftime('%Y-%m-%d %H:%M')}")
                    rprint(f"  Optimizer: {run.optimizer_type} | Examples: {run.training_examples}")

                    if run.status == "completed":
                        rprint(f"  Score: {run.baseline_score:.4f} → {run.optimized_score:.4f} ({run.improvement_pct:+.1%})")

                    if verbose:
                        rprint(f"  ID: {run.id}")
                        if run.error:
                            rprint(f"  [red]Error: {run.error}[/red]")

                    rprint()
        finally:
            from sia.db.connection import close_db
            await close_db()

    asyncio.run(_history())


@optimize_app.command("compare")
def optimize_compare(
    run_id_1: Annotated[str, typer.Argument(help="First run ID")],
    run_id_2: Annotated[str, typer.Argument(help="Second run ID")],
) -> None:
    """Compare two optimization runs."""
    from uuid import UUID
    from sia.optimization import OptimizationRunner
    from sia.db import init_db

    async def _compare() -> None:
        try:
            db = await init_db()
            async with db.session() as session:
                runner = OptimizationRunner(session=session)

                comparison = runner.compare_runs(UUID(run_id_1), UUID(run_id_2))

                if "error" in comparison:
                    rprint(f"[red]{comparison['error']}[/red]")
                    raise typer.Exit(1)

                rprint("\n[bold]Optimization Comparison[/bold]\n")

                table = Table()
                table.add_column("Metric")
                table.add_column(f"Run 1 ({run_id_1[:8]})", justify="right")
                table.add_column(f"Run 2 ({run_id_2[:8]})", justify="right")

                r1 = comparison["run_1"]
                r2 = comparison["run_2"]

                table.add_row("Baseline Score", f"{r1['baseline_score']:.4f}", f"{r2['baseline_score']:.4f}")
                table.add_row("Optimized Score", f"{r1['optimized_score']:.4f}", f"{r2['optimized_score']:.4f}")
                table.add_row("Improvement", f"{r1['improvement']:+.4f}", f"{r2['improvement']:+.4f}")
                table.add_row("Improvement %", f"{r1['improvement_pct']:+.1%}", f"{r2['improvement_pct']:+.1%}")

                console.print(table)

                comp = comparison["comparison"]
                better = "Run 1" if comp["better_run"] == run_id_1 else "Run 2"
                rprint(f"\n[bold]Winner:[/bold] {better} (by {abs(comp['score_difference']):.4f})")
        finally:
            from sia.db.connection import close_db
            await close_db()

    asyncio.run(_compare())


@optimize_app.command("deploy")
def optimize_deploy(
    run_id: Annotated[str, typer.Argument(help="Run ID to deploy")],
    confirm: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Deploy an optimized module to production."""
    from uuid import UUID
    from sia.optimization import OptimizationRunner
    from sia.db import init_db

    async def _deploy() -> None:
        try:
            db = await init_db()
            async with db.session() as session:
                runner = OptimizationRunner(session=session)
                run = runner.get_run(UUID(run_id))

                if not run:
                    rprint(f"[red]Run '{run_id}' not found[/red]")
                    raise typer.Exit(1)

                if run.status != "completed":
                    rprint(f"[red]Cannot deploy run with status '{run.status}'[/red]")
                    raise typer.Exit(1)

                if not confirm:
                    rprint(f"\n[bold]Deploy Optimization[/bold]")
                    rprint(f"  Agent: {run.agent_name}")
                    rprint(f"  Improvement: {run.improvement_pct:+.1%}")
                    rprint(f"  New score: {run.optimized_score:.4f}")

                    if not typer.confirm("\nProceed with deployment?"):
                        rprint("[yellow]Cancelled[/yellow]")
                        return

                success = await runner.deploy_optimization(UUID(run_id))

                if success:
                    rprint(f"[green]✓[/green] Optimization deployed successfully!")
                else:
                    rprint(f"[red]✗[/red] Deployment failed")
                    raise typer.Exit(1)
        finally:
            from sia.db.connection import close_db
            await close_db()

    asyncio.run(_deploy())


@optimize_app.command("modules")
def optimize_modules() -> None:
    """List available DSPy modules for optimization."""
    from sia.optimization import list_modules, list_metrics

    rprint("\n[bold]Available Modules:[/bold]")
    for name in list_modules():
        rprint(f"  • {name}")

    rprint("\n[bold]Available Metrics:[/bold]")
    for name in list_metrics():
        rprint(f"  • {name}")


# ============================================================================
# Evolution Commands
# ============================================================================

evolve_app = typer.Typer(help="Code evolution commands (self-modification)")
app.add_typer(evolve_app, name="evolve")


@evolve_app.command("propose")
def evolve_propose(
    code_file: Annotated[str, typer.Argument(help="Path to code file to evolve")],
    strategy: Annotated[
        str,
        typer.Option("--strategy", "-s", help="Mutation strategy (random, llm_guided, evolutionary)"),
    ] = "llm_guided",
    verbose: verbose_option = False,
) -> None:
    """Propose code mutations for a file."""
    from pathlib import Path
    from sia.evolution import get_strategy, list_strategies

    code_path = Path(code_file)
    if not code_path.exists():
        rprint(f"[red]File not found: {code_file}[/red]")
        raise typer.Exit(1)

    code = code_path.read_text()

    if strategy not in list_strategies():
        rprint(f"[red]Unknown strategy: {strategy}[/red]")
        rprint(f"Available: {', '.join(list_strategies())}")
        raise typer.Exit(1)

    mutation_strategy = get_strategy(strategy)
    proposals = mutation_strategy.propose_mutations(code)

    if not proposals:
        rprint("[yellow]No mutations proposed[/yellow]")
        return

    rprint(f"\n[bold]Mutation Proposals ({len(proposals)}):[/bold]\n")

    for i, proposal in enumerate(proposals, 1):
        confidence_style = "green" if proposal.confidence >= 0.7 else "yellow" if proposal.confidence >= 0.4 else "red"
        risk_style = "green" if proposal.risk_level == "low" else "yellow" if proposal.risk_level == "medium" else "red"

        rprint(f"[bold cyan]{i}. {proposal.strategy}[/bold cyan]")
        rprint(f"   Confidence: [{confidence_style}]{proposal.confidence:.0%}[/{confidence_style}]")
        rprint(f"   Risk: [{risk_style}]{proposal.risk_level}[/{risk_style}]")
        rprint(f"   Rationale: {proposal.rationale}")

        if verbose:
            rprint(f"   ID: {proposal.id}")
            for j, mutation in enumerate(proposal.mutations, 1):
                rprint(f"   Mutation {j}: {mutation.description}")
                if mutation.target:
                    rprint(f"     Target: {mutation.target}")

        rprint()


@evolve_app.command("validate")
def evolve_validate(
    code_file: Annotated[str, typer.Argument(help="Path to code file to validate")],
    strict: Annotated[bool, typer.Option("--strict", help="Enable strict mode (type checking)")] = False,
    verbose: verbose_option = False,
) -> None:
    """Validate code for syntax, types, and security."""
    from pathlib import Path
    from sia.evolution import validate_code, CodeValidator

    code_path = Path(code_file)
    if not code_path.exists():
        rprint(f"[red]File not found: {code_file}[/red]")
        raise typer.Exit(1)

    code = code_path.read_text()

    validator = CodeValidator(
        enable_type_checking=strict,
        enable_security_checking=True,
        security_level="high" if strict else "medium",
    )
    result = validator.validate(code)

    if result.valid:
        rprint(f"[green]✓[/green] Code is valid")
    else:
        rprint(f"[red]✗[/red] Code has issues")

    rprint(f"\n[bold]Scores:[/bold]")
    rprint(f"  Syntax: {result.syntax_score:.0%}")
    rprint(f"  Security: {result.security_score:.0%}")
    rprint(f"  Overall: {result.overall_score:.0%}")

    if result.issues:
        rprint(f"\n[bold]Issues ({len(result.issues)}):[/bold]")
        for issue in result.issues[:10]:  # Show first 10
            severity_style = {
                "error": "red",
                "warning": "yellow",
                "info": "dim",
            }.get(issue.severity, "")

            line_info = f":{issue.line}" if issue.line else ""
            rprint(f"  [{severity_style}]{issue.severity.upper()}[/{severity_style}] {code_path}{line_info}")
            rprint(f"    {issue.message}")
            if issue.suggestion and verbose:
                rprint(f"    [dim]Suggestion: {issue.suggestion}[/dim]")

        if len(result.issues) > 10:
            rprint(f"  [dim]... and {len(result.issues) - 10} more issues[/dim]")


@evolve_app.command("run")
def evolve_run(
    code_file: Annotated[str, typer.Argument(help="Path to code file to evolve")],
    agent_id: Annotated[str, typer.Option("--agent", "-a", help="Agent ID")] = "default",
    auto_deploy: Annotated[bool, typer.Option("--auto-deploy", help="Auto-deploy if improved")] = False,
    verbose: verbose_option = False,
) -> None:
    """Run a full evolution cycle on code."""
    from pathlib import Path
    from sia.evolution import EvolutionOrchestrator, EvolutionConfig

    code_path = Path(code_file)
    if not code_path.exists():
        rprint(f"[red]File not found: {code_file}[/red]")
        raise typer.Exit(1)

    code = code_path.read_text()

    config = EvolutionConfig(
        auto_deploy=auto_deploy,
        require_human_approval=not auto_deploy,
    )

    orchestrator = EvolutionOrchestrator(config=config)

    async def _evolve() -> None:
        attempt = await orchestrator.evolve(code=code, agent_id=agent_id)

        status_style = {
            "approved": "green",
            "rejected": "red",
            "deployed": "magenta",
            "failed": "red",
        }.get(attempt.status.value, "yellow")

        rprint(f"\n[bold]Evolution Result:[/bold]")
        rprint(f"  Status: [{status_style}]{attempt.status.value.upper()}[/{status_style}]")
        rprint(f"  Strategy: {attempt.strategy_name}")

        if attempt.validation_result:
            rprint(f"  Validation: {attempt.validation_result.overall_score:.0%}")

        if attempt.improvement:
            for metric, value in attempt.improvement.items():
                change_style = "green" if value > 0 else "red" if value < 0 else "dim"
                rprint(f"  {metric.title()}: [{change_style}]{value:+.1%}[/{change_style}]")

        if attempt.rejection_reason:
            rprint(f"  [yellow]Reason: {attempt.rejection_reason}[/yellow]")

        if verbose:
            rprint(f"\n  ID: {attempt.id}")
            if attempt.proposal:
                rprint(f"  Mutations: {len(attempt.proposal.mutations)}")

        rprint()

    asyncio.run(_evolve())


@evolve_app.command("history")
def evolve_history(
    agent_id: Annotated[str, typer.Option("--agent", "-a", help="Filter by agent ID")] = "",
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 10,
) -> None:
    """Show evolution history."""
    # This would normally load from database
    rprint("[dim]Evolution history stored in memory (database storage in Phase 11)[/dim]")
    rprint("[yellow]No evolution attempts recorded yet[/yellow]")


@evolve_app.command("rollback")
def evolve_rollback(
    steps: Annotated[int, typer.Option("--steps", "-s", help="Steps to rollback")] = 1,
    to_version: Annotated[Optional[str], typer.Option("--to", help="Rollback to specific version")] = None,
    to_baseline: Annotated[bool, typer.Option("--baseline", help="Rollback to baseline")] = False,
    agent_id: Annotated[str, typer.Option("--agent", "-a", help="Agent ID")] = "default",
    confirm: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Rollback to a previous code version."""
    from sia.evolution import RollbackManager

    manager = RollbackManager(agent_id=agent_id)

    if not manager.snapshots:
        rprint("[yellow]No snapshots available for rollback[/yellow]")
        return

    if to_baseline:
        target = "baseline"
        result = manager.rollback_to_baseline()
    elif to_version:
        target = to_version
        result = manager.rollback_to_version(to_version)
    else:
        target = f"{steps} step(s) back"
        result = manager.rollback(steps=steps)

    if result.success:
        rprint(f"[green]✓[/green] Rolled back to {target}")
        rprint(f"  Previous: {result.previous_version}")
        rprint(f"  Now: {result.rolled_back_to}")
        if result.changes_lost > 0:
            rprint(f"  [yellow]Versions skipped: {result.changes_lost}[/yellow]")
    else:
        rprint(f"[red]✗[/red] Rollback failed: {result.message}")
        raise typer.Exit(1)


@evolve_app.command("versions")
def evolve_versions(
    agent_id: Annotated[str, typer.Option("--agent", "-a", help="Agent ID")] = "default",
) -> None:
    """List code versions for an agent."""
    from sia.evolution import RollbackManager

    manager = RollbackManager(agent_id=agent_id)
    versions = manager.list_versions()

    if not versions:
        rprint("[yellow]No versions recorded[/yellow]")
        return

    table = Table(title=f"Code Versions: {agent_id}")
    table.add_column("Version", style="cyan")
    table.add_column("Source")
    table.add_column("Description", width=40)
    table.add_column("Hash", style="dim")
    table.add_column("Current")
    table.add_column("Baseline")

    for v in versions:
        desc = v["description"][:40] if v["description"] else ""
        current = "[green]●[/green]" if v["is_current"] else ""
        baseline = "[blue]●[/blue]" if v["is_baseline"] else ""

        table.add_row(
            v["version"],
            v["source"],
            desc,
            v["code_hash"][:8],
            current,
            baseline,
        )

    console.print(table)


@evolve_app.command("strategies")
def evolve_strategies() -> None:
    """List available mutation strategies."""
    from sia.evolution import list_strategies

    rprint("\n[bold]Available Mutation Strategies:[/bold]")
    for name in list_strategies():
        rprint(f"  • {name}")

    rprint("\n[bold]Strategy Descriptions:[/bold]")
    rprint("  [cyan]random[/cyan] - Random mutations for exploration")
    rprint("  [cyan]llm_guided[/cyan] - LLM-based intelligent improvements")
    rprint("  [cyan]error_fix[/cyan] - Specialized for fixing errors")
    rprint("  [cyan]evolutionary[/cyan] - Genetic algorithm approach")
    rprint("  [cyan]crossover[/cyan] - Combine code from multiple versions")
    rprint("  [cyan]uniform_crossover[/cyan] - Uniform crossover at statement level")


# ============================================================================
# API Commands
# ============================================================================

api_app = typer.Typer(help="API server commands")
app.add_typer(api_app, name="api")


@api_app.command("serve")
def api_serve(
    host: Annotated[
        Optional[str],
        typer.Option("--host", "-h", help="Host to bind to"),
    ] = None,
    port: Annotated[
        Optional[int],
        typer.Option("--port", "-p", help="Port to bind to"),
    ] = None,
    reload: Annotated[
        bool,
        typer.Option("--reload/--no-reload", help="Enable auto-reload"),
    ] = True,
) -> None:
    """Start the API server."""
    import uvicorn

    config = get_config()
    host = host or config.api.host
    port = port or config.api.port

    rprint(f"[green]Starting SIA API server at http://{host}:{port}[/green]")

    uvicorn.run(
        "sia.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


# ============================================================================
# Config Commands
# ============================================================================

config_app = typer.Typer(help="Configuration commands")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show(
    section: Annotated[
        Optional[str],
        typer.Argument(help="Config section to show (database, ollama, api, etc.)"),
    ] = None,
) -> None:
    """Show current configuration."""
    config = get_config()

    if section:
        if hasattr(config, section):
            section_config = getattr(config, section)
            rprint(f"\n[bold]{section}:[/bold]")
            for key, value in section_config.model_dump().items():
                # Mask sensitive values
                if "key" in key.lower() or "password" in key.lower() or "secret" in key.lower():
                    value = "***" if value else None
                rprint(f"  {key}: {value}")
        else:
            rprint(f"[red]Unknown section: {section}[/red]")
            raise typer.Exit(1)
    else:
        # Show all sections
        for section_name in ["database", "ollama", "embedding", "api", "execution", "dspy"]:
            section_config = getattr(config, section_name)
            rprint(f"\n[bold]{section_name}:[/bold]")
            for key, value in section_config.model_dump().items():
                if "key" in key.lower() or "password" in key.lower() or "secret" in key.lower():
                    value = "***" if value else None
                rprint(f"  {key}: {value}")


if __name__ == "__main__":
    app()
