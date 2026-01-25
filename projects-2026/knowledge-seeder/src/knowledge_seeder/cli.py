"""Knowledge Seeder CLI."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from knowledge_seeder import __version__
from knowledge_seeder.config import get_settings
from knowledge_seeder.extractor_service import ExtractorService
from knowledge_seeder.kas_client import KASClient, build_kas_payload
from knowledge_seeder.logging_config import configure_logging, LogFormat
from knowledge_seeder.models import SourceStatus, ValidationResult
from knowledge_seeder.quality import score_content
from knowledge_seeder.source_parser import SourceParser
from knowledge_seeder.state import StateManager

app = typer.Typer(
    name="knowledge-seeder",
    help="CLI tool for batch ingestion of knowledge sources.",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        rprint(f"knowledge-seeder v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
    log_level: str = typer.Option(
        "WARNING",
        "--log-level",
        "-L",
        help="Log level (DEBUG, INFO, WARNING, ERROR).",
    ),
    log_json: bool = typer.Option(
        False,
        "--log-json",
        help="Output logs as JSON (for log aggregation).",
    ),
) -> None:
    """Knowledge Seeder - Batch ingestion tool for Knowledge Engine."""
    # Configure logging
    log_format = LogFormat.JSON if log_json else LogFormat.RICH
    configure_logging(level=log_level, format=log_format)


# --- Validate Command ---


@app.command()
def validate(
    paths: list[Path] = typer.Argument(
        ...,
        help="YAML source files to validate.",
        exists=True,
    ),
    check_urls: bool = typer.Option(
        False,
        "--check-urls",
        "-u",
        help="Check if URLs are accessible (slower).",
    ),
) -> None:
    """Validate YAML source files."""
    parser = SourceParser()
    all_results: list[ValidationResult] = []
    errors = 0
    warnings = 0

    for path in paths:
        rprint(f"\n[bold]Validating {path.name}...[/bold]")

        try:
            results = parser.validate_file(path)
            all_results.extend(results)

            for result in results:
                if not result.is_valid:
                    errors += 1
                    rprint(f"  [red]INVALID[/red] {result.name}: {result.error}")
                elif result.warnings:
                    warnings += len(result.warnings)
                    for w in result.warnings:
                        rprint(f"  [yellow]WARNING[/yellow] {result.name}: {w}")

        except Exception as e:
            errors += 1
            rprint(f"  [red]ERROR[/red] Failed to parse: {e}")

    # Check URL accessibility if requested
    if check_urls:
        rprint("\n[bold]Checking URL accessibility...[/bold]")
        asyncio.run(_check_urls(all_results))

    # Summary
    rprint(f"\n[bold]Summary:[/bold]")
    rprint(f"  Sources: {len(all_results)}")
    rprint(f"  Errors: [red]{errors}[/red]" if errors else f"  Errors: {errors}")
    rprint(f"  Warnings: [yellow]{warnings}[/yellow]" if warnings else f"  Warnings: {warnings}")

    if errors > 0:
        raise typer.Exit(1)


async def _check_urls(results: list[ValidationResult]) -> None:
    """Check URL accessibility for validation results."""
    async with ExtractorService() as service:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Checking URLs...", total=len(results))

            for result in results:
                if result.is_valid:
                    from knowledge_seeder.models import Source, SourceType

                    # Create minimal source for checking
                    source = Source(
                        name=result.name,
                        url=result.url,
                        source_type=service.detect_type(result.url) or SourceType.URL,
                    )

                    accessible, error = await service.check_accessible(source)
                    result.is_accessible = accessible

                    if not accessible:
                        rprint(f"  [red]UNREACHABLE[/red] {result.name}: {error}")

                progress.advance(task)


# --- Fetch Command (dry-run extraction) ---


@app.command()
def fetch(
    url: str = typer.Argument(..., help="URL to fetch and extract."),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Extract content without storing (default: dry-run).",
    ),
) -> None:
    """Fetch and extract content from a URL (for testing)."""
    asyncio.run(_fetch(url, dry_run))


async def _fetch(url: str, dry_run: bool) -> None:
    """Async fetch implementation."""
    rprint(f"[bold]Fetching:[/bold] {url}")

    async with ExtractorService() as service:
        # Detect type
        source_type = service.detect_type(url)
        if source_type:
            rprint(f"[bold]Detected type:[/bold] {source_type.value}")
        else:
            rprint("[yellow]Could not detect source type[/yellow]")
            return

        # Extract
        try:
            with console.status("Extracting content..."):
                result = await service.extract_url(url)

            rprint(f"\n[bold green]Extraction successful![/bold green]")
            rprint(f"  Title: {result.title or '(none)'}")
            rprint(f"  Length: {result.content_length:,} characters")
            rprint(f"  Valid: {'Yes' if result.is_valid else 'No'}")

            # Show metadata
            if result.metadata:
                rprint(f"\n[bold]Metadata:[/bold]")
                for key, value in result.metadata.items():
                    if value:
                        rprint(f"  {key}: {value}")

            # Show preview
            rprint(f"\n[bold]Preview:[/bold]")
            rprint(f"  {result.preview}")

            if dry_run:
                rprint(f"\n[dim](dry-run mode - content not stored)[/dim]")

        except Exception as e:
            rprint(f"\n[red]Extraction failed:[/red] {e}")
            raise typer.Exit(1)


# --- Quality Command ---


@app.command()
def quality(
    url: str = typer.Argument(..., help="URL to fetch and score."),
) -> None:
    """Fetch content and score its quality."""
    asyncio.run(_quality(url))


async def _quality(url: str) -> None:
    """Async quality implementation."""
    rprint(f"[bold]Fetching:[/bold] {url}")

    async with ExtractorService() as service:
        try:
            with console.status("Extracting content..."):
                result = await service.extract_url(url)

            # Score content quality
            quality_result = score_content(
                result.content,
                source_type=result.source_type.value if result.source_type else None,
            )

            rprint(f"\n[bold]Quality Assessment:[/bold]")

            # Grade with color
            grade_colors = {"A": "green", "B": "cyan", "C": "yellow", "D": "orange1", "F": "red"}
            grade_color = grade_colors.get(quality_result.grade, "white")
            rprint(f"  Overall Score: [{grade_color}]{quality_result.score:.1f}/100 (Grade {quality_result.grade})[/{grade_color}]")
            rprint(f"  Acceptable: {'[green]Yes[/green]' if quality_result.is_acceptable else '[red]No[/red]'}")

            # Component scores
            rprint(f"\n[bold]Component Scores:[/bold]")
            rprint(f"  Length:     {quality_result.length_score:.1f}/100")
            rprint(f"  Density:    {quality_result.density_score:.1f}/100")
            rprint(f"  Structure:  {quality_result.structure_score:.1f}/100")
            rprint(f"  Language:   {quality_result.language_score:.1f}/100")
            rprint(f"  Uniqueness: {quality_result.uniqueness_score:.1f}/100")

            # Metrics
            rprint(f"\n[bold]Content Metrics:[/bold]")
            rprint(f"  Word Count:         {quality_result.word_count:,}")
            rprint(f"  Sentence Count:     {quality_result.sentence_count:,}")
            rprint(f"  Avg Sentence Len:   {quality_result.avg_sentence_length:.1f} words")
            rprint(f"  Code Ratio:         {quality_result.code_ratio:.1%}")
            rprint(f"  Link Density:       {quality_result.link_density:.1%}")

            # Issues and suggestions
            if quality_result.issues:
                rprint(f"\n[bold yellow]Issues:[/bold yellow]")
                for issue in quality_result.issues:
                    rprint(f"  - {issue}")

            if quality_result.suggestions:
                rprint(f"\n[bold cyan]Suggestions:[/bold cyan]")
                for suggestion in quality_result.suggestions:
                    rprint(f"  - {suggestion}")

        except Exception as e:
            rprint(f"\n[red]Failed:[/red] {e}")
            raise typer.Exit(1)


# --- Status Command ---


@app.command()
def status(
    namespace: Optional[str] = typer.Option(
        None,
        "--namespace",
        "-n",
        help="Filter by namespace.",
    ),
) -> None:
    """Show ingestion status."""
    asyncio.run(_status(namespace))


async def _status(namespace: str | None) -> None:
    """Async status implementation."""
    settings = get_settings()

    # Check if state database exists
    if not settings.state_db_path.exists():
        rprint("[yellow]No state database found. Run 'sync' to initialize.[/yellow]")
        rprint(f"[dim]Expected at: {settings.state_db_path}[/dim]")
        return

    async with StateManager() as state:
        # Get stats
        stats = await state.get_stats(namespace)
        namespaces = await state.get_namespaces()

        # Display stats table
        table = Table(title="Ingestion Status")
        table.add_column("Status", style="bold")
        table.add_column("Count", justify="right")

        status_colors = {
            "pending": "white",
            "extracting": "blue",
            "extracted": "cyan",
            "ingesting": "blue",
            "completed": "green",
            "failed": "red",
            "skipped": "yellow",
        }

        for status_name, count in stats.items():
            if status_name == "total":
                continue
            color = status_colors.get(status_name, "white")
            table.add_row(status_name.capitalize(), f"[{color}]{count}[/{color}]")

        table.add_row("─" * 12, "─" * 6, style="dim")
        table.add_row("[bold]Total[/bold]", f"[bold]{stats['total']}[/bold]")

        console.print(table)

        # Show namespaces
        if namespaces:
            rprint(f"\n[bold]Namespaces:[/bold] {', '.join(namespaces)}")

        # Show filter
        if namespace:
            rprint(f"[dim](filtered by namespace: {namespace})[/dim]")


# --- List Command ---


@app.command("list")
def list_sources(
    namespace: Optional[str] = typer.Option(
        None,
        "--namespace",
        "-n",
        help="Filter by namespace.",
    ),
    status_filter: Optional[str] = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status (pending, completed, failed, etc.).",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-l",
        help="Maximum number of sources to show.",
    ),
) -> None:
    """List sources in the state database."""
    asyncio.run(_list_sources(namespace, status_filter, limit))


async def _list_sources(
    namespace: str | None,
    status_filter: str | None,
    limit: int,
) -> None:
    """Async list implementation."""
    settings = get_settings()

    if not settings.state_db_path.exists():
        rprint("[yellow]No state database found.[/yellow]")
        return

    async with StateManager() as state:
        # Parse status filter
        status = None
        if status_filter:
            try:
                status = SourceStatus(status_filter.lower())
            except ValueError:
                rprint(f"[red]Invalid status: {status_filter}[/red]")
                rprint(f"Valid values: {', '.join(s.value for s in SourceStatus)}")
                raise typer.Exit(1)

        # Get sources
        sources = await state.list_sources(
            namespace=namespace,
            status=status,
            limit=limit,
        )

        if not sources:
            rprint("[dim]No sources found matching criteria.[/dim]")
            return

        # Display table
        table = Table(title=f"Sources (showing {len(sources)})")
        table.add_column("Name", style="bold", max_width=30)
        table.add_column("Namespace", max_width=20)
        table.add_column("Status")
        table.add_column("Chunks", justify="right")

        status_colors = {
            SourceStatus.PENDING: "white",
            SourceStatus.EXTRACTING: "blue",
            SourceStatus.EXTRACTED: "cyan",
            SourceStatus.INGESTING: "blue",
            SourceStatus.COMPLETED: "green",
            SourceStatus.FAILED: "red",
            SourceStatus.SKIPPED: "yellow",
        }

        for source in sources:
            color = status_colors.get(source.status, "white")
            chunks = str(source.chunk_count) if source.chunk_count else "-"
            table.add_row(
                source.name,
                source.namespace,
                f"[{color}]{source.status.value}[/{color}]",
                chunks,
            )

        console.print(table)


# --- Failed Command ---


@app.command()
def failed(
    namespace: Optional[str] = typer.Option(
        None,
        "--namespace",
        "-n",
        help="Filter by namespace.",
    ),
) -> None:
    """Show failed sources with error details."""
    asyncio.run(_failed(namespace))


async def _failed(namespace: str | None) -> None:
    """Async failed implementation."""
    settings = get_settings()

    if not settings.state_db_path.exists():
        rprint("[yellow]No state database found.[/yellow]")
        return

    async with StateManager() as state:
        sources = await state.get_failed_sources(namespace=namespace)

        if not sources:
            rprint("[green]No failed sources![/green]")
            return

        rprint(f"[bold red]Failed Sources ({len(sources)}):[/bold red]\n")

        for source in sources:
            rprint(f"[bold]{source.name}[/bold] ({source.namespace})")
            rprint(f"  URL: {source.url}")
            rprint(f"  Error: [red]{source.error_message}[/red]")
            rprint(f"  Retries: {source.retry_count}")
            rprint()


# --- Count Command ---


@app.command()
def count(
    paths: list[Path] = typer.Argument(
        ...,
        help="YAML source files to count.",
        exists=True,
    ),
) -> None:
    """Count sources in YAML files."""
    parser = SourceParser()
    counts = parser.count_sources(paths)

    # By namespace table
    table = Table(title="Sources by Namespace")
    table.add_column("Namespace", style="bold")
    table.add_column("Count", justify="right")

    for ns, count in sorted(counts["by_namespace"].items()):
        table.add_row(ns, str(count))

    table.add_row("─" * 20, "─" * 6, style="dim")
    table.add_row("[bold]Total[/bold]", f"[bold]{counts['total']}[/bold]")

    console.print(table)

    # By type
    rprint(f"\n[bold]By Type:[/bold]")
    for st, count in sorted(counts["by_type"].items()):
        rprint(f"  {st}: {count}")

    if counts["placeholders"] > 0:
        rprint(f"\n[yellow]Placeholders: {counts['placeholders']}[/yellow]")


# --- Init Command ---


@app.command()
def init() -> None:
    """Initialize the state database."""
    asyncio.run(_init())


async def _init() -> None:
    """Async init implementation."""
    settings = get_settings()

    rprint(f"[bold]Initializing state database...[/bold]")
    rprint(f"  Location: {settings.state_db_path}")

    async with StateManager() as state:
        # Connection will create schema
        pass

    rprint(f"[green]State database initialized![/green]")


# --- Sync Command (placeholder for now) ---


@app.command()
def sync(
    paths: list[Path] = typer.Argument(
        ...,
        help="YAML source files to sync.",
        exists=True,
    ),
    namespace: Optional[str] = typer.Option(
        None,
        "--namespace",
        "-n",
        help="Override namespace for all sources.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be synced without making changes.",
    ),
    extract_only: bool = typer.Option(
        False,
        "--extract-only",
        help="Only extract content, don't ingest to Knowledge Engine.",
    ),
) -> None:
    """Sync sources from YAML files to the state database.

    This command:
    1. Parses YAML source files
    2. Adds new sources to the state database
    3. Extracts content from pending sources
    4. (When connected) Ingests to Knowledge Engine
    """
    asyncio.run(_sync(paths, namespace, dry_run, extract_only))


async def _sync(
    paths: list[Path],
    namespace: str | None,
    dry_run: bool,
    extract_only: bool,
) -> None:
    """Async sync implementation with KAS ingestion."""
    parser = SourceParser()
    settings = get_settings()
    kas_client = KASClient()

    # Check KAS health first (unless dry-run)
    if not dry_run and not extract_only:
        try:
            health = await kas_client.health()
            if health.get("status") != "healthy":
                rprint("[red]ERROR: KAS is not healthy[/red]")
                raise typer.Exit(1)
            rprint(f"[green]KAS Status:[/green] {health.get('status')} ({health.get('stats', {}).get('total_content', 0)} docs)")
        except Exception as e:
            rprint(f"[red]ERROR: Cannot connect to KAS at {kas_client.base_url}[/red]")
            rprint(f"[dim]{e}[/dim]")
            raise typer.Exit(1)

    # Parse all source files (only active sources)
    rprint("[bold]Parsing source files...[/bold]")
    all_sources = parser.get_all_sources(paths, include_inactive=False)

    # Override namespace if specified
    if namespace:
        for source in all_sources:
            source.namespace = namespace

    rprint(f"  Found {len(all_sources)} active sources")

    if dry_run:
        rprint("\n[yellow]DRY RUN - no changes will be made[/yellow]")
        rprint(f"\nWould sync {len(all_sources)} sources to KAS.")

        # Show breakdown by namespace
        ns_counts: dict[str, int] = {}
        for source in all_sources:
            ns_counts[source.namespace] = ns_counts.get(source.namespace, 0) + 1
        rprint("\n[bold]By namespace:[/bold]")
        for ns, count in sorted(ns_counts.items()):
            rprint(f"  {ns}: {count}")
        return

    # Initialize state database
    async with StateManager() as state:
        # Add sources to state
        new_count = 0
        existing_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Adding sources to state...", total=len(all_sources))

            for source in all_sources:
                existing = await state.get_source(source.source_id)

                if existing is None:
                    # New source
                    from knowledge_seeder.models import SourceState

                    source_state = SourceState(
                        source_id=source.source_id,
                        name=source.name,
                        url=source.url,
                        namespace=source.namespace,
                        source_type=source.source_type,
                        status=SourceStatus.PENDING,
                    )
                    await state.upsert_source(source_state)
                    new_count += 1
                else:
                    existing_count += 1

                progress.advance(task)

        rprint(f"\n[bold]State database updated:[/bold]")
        rprint(f"  New sources: [green]{new_count}[/green]")
        rprint(f"  Existing: {existing_count}")

        # Get pending sources for extraction
        pending = await state.get_pending_sources()

        if not pending:
            rprint("\n[dim]No pending sources to extract.[/dim]")
            return

        rprint(f"\n[bold]Processing {len(pending)} pending sources...[/bold]")

        async with ExtractorService() as extractor:
            extracted = 0
            ingested = 0
            failed = 0
            skipped = 0

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Processing...", total=len(pending))

                for source_state in pending:
                    progress.update(task, description=f"Processing {source_state.name}...")

                    try:
                        # Create source object for extraction
                        from knowledge_seeder.models import Source

                        source = Source(
                            name=source_state.name,
                            url=source_state.url,
                            source_type=source_state.source_type,
                            namespace=source_state.namespace,
                        )

                        # Update status
                        await state.update_status(source_state.source_id, SourceStatus.EXTRACTING)

                        # Extract content
                        result = await extractor.extract(source)

                        if not result.is_valid:
                            await state.mark_failed(
                                source_state.source_id,
                                f"Content too short ({result.content_length} chars)",
                            )
                            skipped += 1
                            progress.advance(task)
                            continue

                        # Mark as extracted
                        content_hash = StateManager.compute_content_hash(result.content)
                        await state.mark_extracted(
                            source_state.source_id,
                            content_hash,
                            result.content_length,
                        )
                        extracted += 1

                        # Skip KAS ingestion if extract-only
                        if extract_only:
                            progress.advance(task)
                            await asyncio.sleep(settings.rate_limit_delay)
                            continue

                        # Score quality
                        quality_result = score_content(
                            result.content,
                            source_type=result.source_type.value if result.source_type else None,
                        )

                        # Build KAS payload
                        await state.update_status(source_state.source_id, SourceStatus.INGESTING)

                        payload = build_kas_payload(
                            content=result.content,
                            title=result.title or source_state.name,
                            document_type="markdown",
                            namespace=source_state.namespace,
                            source_url=source_state.url,
                            tags=[],  # Tags not in source_state
                            source_id=source_state.source_id,
                            source_type=source_state.source_type.value,
                            priority="P2",  # Default priority
                            quality_score=quality_result.score,
                            quality_grade=quality_result.grade,
                        )

                        # Ingest to KAS
                        response = await kas_client.ingest_document(payload)

                        if response.get("success"):
                            chunks = response.get("chunks_created", 0)
                            await state.mark_completed(
                                source_state.source_id,
                                response.get("content_id", ""),
                                chunks,
                            )
                            ingested += 1
                        elif "duplicate" in str(response.get("message", "")).lower():
                            # Treat duplicates as success
                            await state.update_status(source_state.source_id, SourceStatus.COMPLETED)
                            ingested += 1
                        else:
                            error = response.get("message") or response.get("detail", "Unknown error")
                            await state.mark_failed(source_state.source_id, error[:200])
                            failed += 1

                    except Exception as e:
                        await state.mark_failed(source_state.source_id, str(e)[:200])
                        failed += 1

                    progress.advance(task)

                    # Rate limiting
                    await asyncio.sleep(settings.rate_limit_delay)

        # Summary
        rprint(f"\n[bold]Sync complete:[/bold]")
        rprint(f"  Extracted: [cyan]{extracted}[/cyan]")
        if not extract_only:
            rprint(f"  Ingested:  [green]{ingested}[/green]")
        rprint(f"  Failed:    [red]{failed}[/red]")
        rprint(f"  Skipped:   [yellow]{skipped}[/yellow]")

        if extract_only:
            rprint("\n[dim](extract-only mode - KAS ingestion skipped)[/dim]")
        else:
            # Show final KAS stats
            try:
                stats = await kas_client.stats()
                rprint(f"\n[bold]KAS Status:[/bold] {stats.get('total_content', 0)} documents, {stats.get('total_chunks', 0)} chunks")
            except Exception:
                pass


if __name__ == "__main__":
    app()
