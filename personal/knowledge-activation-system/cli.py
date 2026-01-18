"""Knowledge Activation System CLI."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlparse, urlunparse

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from knowledge.ai import close_ai_provider
from knowledge.config import get_settings
from knowledge.db import close_db, get_db
from knowledge.embeddings import check_ollama_health, close_embedding_service
from knowledge.rerank import close_reranker
from knowledge.search import SearchResult, hybrid_search, search_bm25_only, search_vector_only


def mask_database_url(url: str) -> str:
    """Mask password in database URL for display.

    Args:
        url: Database connection URL potentially containing credentials

    Returns:
        URL with password replaced by ***
    """
    try:
        parsed = urlparse(url)
        if parsed.password:
            # Build netloc without password
            if parsed.username:
                netloc = f"{parsed.username}:***@{parsed.hostname}"
            else:
                netloc = f"***@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return urlunparse(parsed._replace(netloc=netloc))
        return url
    except (ValueError, AttributeError):
        # Fallback: try to mask any password-like patterns via regex
        import re

        return re.sub(r":([^:@]+)@", ":***@", url)


app = typer.Typer(
    name="knowledge",
    help="Knowledge Activation System - Personal knowledge management with hybrid search.",
    no_args_is_help=True,
)
console = Console()


def run_async(coro):
    """Run async coroutine in synchronous CLI context.

    Wrapper around asyncio.run() for running async functions from
    synchronous typer command handlers.

    Args:
        coro: Coroutine object to execute

    Returns:
        Result of the coroutine execution
    """
    return asyncio.run(coro)


# CLI constants for validation
MAX_QUERY_LENGTH = 2000  # Maximum query length in characters
MIN_QUERY_LENGTH = 1  # Minimum query length
MAX_LIMIT = 100  # Maximum results limit
MIN_LIMIT = 1  # Minimum results limit
VALID_SEARCH_MODES = {"hybrid", "bm25", "vector"}


def validate_query(query: str) -> None:
    """Validate search query length and content.

    Args:
        query: User-provided search query

    Raises:
        typer.Exit: If query is invalid
    """
    if not query or len(query.strip()) < MIN_QUERY_LENGTH:
        console.print("[red]Error: Query cannot be empty[/red]")
        raise typer.Exit(1)
    if len(query) > MAX_QUERY_LENGTH:
        console.print(
            f"[red]Error: Query too long ({len(query)} chars). "
            f"Maximum is {MAX_QUERY_LENGTH} characters.[/red]"
        )
        raise typer.Exit(1)


def validate_limit(limit: int, context: str = "results") -> int:
    """Validate and constrain limit parameter.

    Args:
        limit: User-provided limit
        context: What the limit is for (for error messages)

    Returns:
        Validated limit (clamped to valid range)
    """
    if limit < MIN_LIMIT:
        console.print(f"[yellow]Warning: Limit must be at least {MIN_LIMIT}. Using {MIN_LIMIT}.[/yellow]")
        return MIN_LIMIT
    if limit > MAX_LIMIT:
        console.print(f"[yellow]Warning: Limit cannot exceed {MAX_LIMIT}. Using {MAX_LIMIT}.[/yellow]")
        return MAX_LIMIT
    return limit


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of results")] = 10,
    mode: Annotated[
        str, typer.Option("--mode", "-m", help="Search mode: hybrid, bm25, vector")
    ] = "hybrid",
    rerank: Annotated[
        bool, typer.Option("--rerank", "-r", help="Rerank results using cross-encoder")
    ] = False,
    rerank_model: Annotated[
        str, typer.Option("--rerank-model", help="Reranker model")
    ] = "mixedbread-ai/mxbai-rerank-base-v1",
) -> None:
    """Search your knowledge base using hybrid search."""
    # Validate inputs
    validate_query(query)
    limit = validate_limit(limit, "search results")

    if mode not in VALID_SEARCH_MODES:
        console.print(f"[red]Error: Invalid mode '{mode}'. Valid modes: {', '.join(VALID_SEARCH_MODES)}[/red]")
        raise typer.Exit(1)

    async def _search():
        try:
            # Check Ollama for modes that need embeddings
            if mode in ("hybrid", "vector"):
                ollama_status = await check_ollama_health()
                if not ollama_status.healthy:
                    console.print(f"[red]Ollama not available: {ollama_status.error}[/red]")
                    console.print("[dim]Use --mode bm25 for text-only search[/dim]")
                    raise typer.Exit(1)

            if mode == "hybrid":
                results = await hybrid_search(query, limit=limit * 2 if rerank else limit)
            elif mode == "bm25":
                results = await search_bm25_only(query, limit=limit * 2 if rerank else limit)
            elif mode == "vector":
                results = await search_vector_only(query, limit=limit * 2 if rerank else limit)
            else:
                console.print(f"[red]Unknown mode: {mode}[/red]")
                raise typer.Exit(1)

            if not results:
                console.print(f"[yellow]No results found for: {query}[/yellow]")
                return

            # Apply reranking if requested
            if rerank:
                try:
                    from knowledge.reranker import rerank_results as local_rerank
                    with console.status("[bold blue]Reranking with cross-encoder..."):
                        results = await local_rerank(
                            query, results, top_k=limit, model_name=rerank_model
                        )
                    console.print(f"[dim]Reranked using {rerank_model}[/dim]\n")
                except ImportError:
                    console.print(
                        "[yellow]Warning: sentence-transformers not installed. "
                        "Install with: uv pip install sentence-transformers[/yellow]\n"
                    )
                    results = results[:limit]

            # Create results table
            table = Table(title=f"Search Results for: {query}")
            table.add_column("Score", style="cyan", width=8)
            table.add_column("Type", style="magenta", width=10)
            table.add_column("Title", style="green")
            table.add_column("Sources", style="dim", width=15)

            for result in results:
                sources = []
                if result.bm25_rank:
                    sources.append(f"BM25:{result.bm25_rank}")
                if result.vector_rank:
                    sources.append(f"Vec:{result.vector_rank}")

                table.add_row(
                    f"{result.score:.4f}",
                    result.content_type,
                    result.title[:60] + "..." if len(result.title) > 60 else result.title,
                    " ".join(sources),
                )

            console.print(table)

            # Show preview of top result
            if results and results[0].chunk_text:
                console.print()
                preview = results[0].chunk_text[:500]
                if len(results[0].chunk_text) > 500:
                    preview += "..."
                console.print(
                    Panel(
                        preview,
                        title=f"[bold]Preview: {results[0].title}[/bold]",
                        border_style="blue",
                    )
                )

        finally:
            await close_db()
            await close_embedding_service()

    run_async(_search())


@app.command()
def ask(
    query: Annotated[str, typer.Argument(help="Question to ask")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Search results to consider")] = 10,
    no_ai: Annotated[bool, typer.Option("--no-ai", help="Skip AI answer generation")] = False,
    instructor: Annotated[
        bool, typer.Option("--instructor", "-i", help="Use Instructor for structured outputs")
    ] = False,
    model: Annotated[
        str, typer.Option("--model", help="Model for Instructor mode")
    ] = "ollama/qwen2.5:7b",
) -> None:
    """Ask a question and get an AI-generated answer with citations."""
    from knowledge.qa import ConfidenceLevel, search_and_summarize
    from knowledge.qa import ask as qa_ask

    async def _ask():
        try:
            # Check Ollama for embeddings
            ollama_status = await check_ollama_health()
            if not ollama_status.healthy:
                console.print(f"[red]Ollama not available: {ollama_status.error}[/red]")
                raise typer.Exit(1)

            if instructor and not no_ai:
                # Use Instructor-based Q&A with structured outputs
                try:
                    from knowledge.qa_instructor import (
                        answer_question,
                        format_response_with_warning,
                        should_show_warning,
                    )
                    from knowledge.search import hybrid_search as hs

                    with console.status("[bold blue]Searching..."):
                        search_results = await hs(query, limit=limit)

                    if not search_results:
                        console.print("[yellow]No relevant content found.[/yellow]")
                        return

                    with console.status(f"[bold blue]Generating answer with {model}..."):
                        response = await answer_question(
                            query, search_results, model=model, max_context_chunks=5
                        )

                    # Display formatted response
                    console.print()
                    console.print(format_response_with_warning(response))
                    return

                except ImportError as e:
                    console.print(
                        f"[yellow]Instructor not available ({e}). "
                        "Install with: uv pip install instructor[/yellow]"
                    )
                    console.print("[dim]Falling back to standard Q&A...[/dim]\n")

            if no_ai:
                # Just search and summarize without AI
                with console.status("[bold blue]Searching..."):
                    result = await search_and_summarize(query, limit=limit)
            else:
                # Full Q&A with AI
                with console.status("[bold blue]Thinking..."):
                    result = await qa_ask(query, limit=limit)

            if result.error:
                console.print(f"[red]Error: {result.error}[/red]")
                raise typer.Exit(1)

            # Show confidence indicator
            confidence_color = {
                ConfidenceLevel.HIGH: "green",
                ConfidenceLevel.MEDIUM: "yellow",
                ConfidenceLevel.LOW: "red",
            }[result.confidence]

            console.print()
            console.print(
                f"[{confidence_color}]Confidence: {result.confidence.value.upper()} "
                f"({result.confidence_score:.2f})[/{confidence_color}]"
            )

            # Show warning if present
            if result.warning:
                console.print(f"[yellow]Warning: {result.warning}[/yellow]")

            console.print()

            # Show answer
            if result.answer:
                console.print(
                    Panel(
                        result.answer,
                        title="[bold]Answer[/bold]",
                        border_style="blue",
                    )
                )

            # Show citations
            if result.citations:
                console.print()
                console.print("[bold]Sources:[/bold]")
                for citation in result.citations:
                    type_badge = f"[dim]{citation.content_type}[/dim]"
                    console.print(f"  [{citation.index}] {citation.title} {type_badge}")

        finally:
            await close_db()
            await close_embedding_service()
            await close_reranker()
            await close_ai_provider()

    run_async(_ask())


@app.command()
def stats() -> None:
    """Show database statistics."""

    async def _stats():
        try:
            db = await get_db()
            stats = await db.get_stats()

            console.print()
            console.print("[bold cyan]Database Statistics[/bold cyan]")
            console.print()

            # Content counts
            table = Table(title="Content by Type")
            table.add_column("Type", style="magenta")
            table.add_column("Count", style="green", justify="right")

            content_by_type = stats.get("content_by_type", {})
            for content_type, count in sorted(content_by_type.items()):
                table.add_row(content_type, str(count))

            if content_by_type:
                console.print(table)
            else:
                console.print("[dim]No content yet[/dim]")

            console.print()

            # Summary stats
            summary = Table(show_header=False, box=None)
            summary.add_column("Metric", style="cyan")
            summary.add_column("Value", style="green", justify="right")

            summary.add_row("Total Content", str(stats.get("total_content", 0)))
            summary.add_row("Total Chunks", str(stats.get("total_chunks", 0)))
            summary.add_row("Active Reviews", str(stats.get("review_active", 0)))
            summary.add_row("Reviews Due", str(stats.get("review_due", 0)))

            console.print(summary)

        finally:
            await close_db()

    run_async(_stats())


@app.command()
def health() -> None:
    """Check health of all services."""

    async def _health():
        console.print()
        console.print("[bold cyan]Service Health Check[/bold cyan]")
        console.print()

        all_healthy = True
        suggestions: list[str] = []

        # Check PostgreSQL
        try:
            db = await get_db()
            db_health = await db.check_health()

            if db_health["status"] == "healthy":
                console.print("[green]✓[/green] PostgreSQL: [green]Healthy[/green]")
                console.print(f"  Extensions: {', '.join(db_health.get('extensions', []))}")
                console.print(f"  Content: {db_health.get('content_count', 0)} items")
                console.print(f"  Chunks: {db_health.get('chunk_count', 0)} chunks")
            else:
                console.print("[red]✗[/red] PostgreSQL: [red]Unhealthy[/red]")
                console.print(f"  Error: {db_health.get('error', 'Unknown')}")
                suggestions.append("Check PostgreSQL logs: docker compose logs db")
                all_healthy = False
        except ConnectionRefusedError:
            console.print("[red]✗[/red] PostgreSQL: [red]Connection Refused[/red]")
            suggestions.append("Start PostgreSQL: docker compose up -d db")
            suggestions.append("Check if port 5432 is available: lsof -i :5432")
            all_healthy = False
        except Exception as e:
            console.print("[red]✗[/red] PostgreSQL: [red]Connection Failed[/red]")
            console.print(f"  Error: {e}")
            error_str = str(e).lower()
            if "password" in error_str or "authentication" in error_str:
                suggestions.append("Check database credentials in .env file")
            elif "connection" in error_str or "refused" in error_str:
                suggestions.append("Start PostgreSQL: docker compose up -d db")
            else:
                suggestions.append("Check database URL: python cli.py config")
            all_healthy = False

        console.print()

        # Check Ollama
        try:
            ollama_status = await check_ollama_health()

            if ollama_status.healthy:
                console.print("[green]✓[/green] Ollama: [green]Healthy[/green]")
                settings = get_settings()
                console.print(f"  Embedding model: {settings.embedding_model}")
                console.print(f"  Available models: {', '.join(ollama_status.models_loaded[:5])}")
                if len(ollama_status.models_loaded) > 5:
                    console.print(f"    ...and {len(ollama_status.models_loaded) - 5} more")
            else:
                console.print("[red]✗[/red] Ollama: [red]Unhealthy[/red]")
                console.print(f"  Error: {ollama_status.error}")
                if "not found" in (ollama_status.error or "").lower():
                    settings = get_settings()
                    suggestions.append(f"Pull embedding model: ollama pull {settings.embedding_model}")
                elif "connect" in (ollama_status.error or "").lower():
                    suggestions.append("Start Ollama: ollama serve")
                all_healthy = False
        except Exception as e:
            console.print("[red]✗[/red] Ollama: [red]Connection Failed[/red]")
            console.print(f"  Error: {e}")
            suggestions.append("Start Ollama: ollama serve")
            suggestions.append("Check Ollama URL in config: python cli.py config")
            all_healthy = False

        console.print()

        # Overall status
        if all_healthy:
            console.print("[bold green]All services healthy![/bold green]")
        else:
            console.print("[bold red]Some services are unhealthy[/bold red]")
            if suggestions:
                console.print()
                console.print("[bold yellow]Suggested fixes:[/bold yellow]")
                for suggestion in suggestions:
                    console.print(f"  → {suggestion}")
            raise typer.Exit(1)

        await close_db()
        await close_embedding_service()

    run_async(_health())


@app.command()
def config(
    validate: Annotated[bool, typer.Option("--validate", help="Validate configuration")] = False,
    show_all: Annotated[bool, typer.Option("--all", "-a", help="Show all settings")] = False,
) -> None:
    """Show or validate current configuration."""
    if validate:
        # Validate configuration
        console.print("[bold cyan]Validating Configuration...[/bold cyan]")
        console.print()

        errors = []
        warnings = []

        try:
            settings = get_settings()

            # Check database URL
            if not settings.database_url:
                errors.append("DATABASE_URL not set")
            elif "localhost" in settings.database_url or "127.0.0.1" in settings.database_url:
                warnings.append("Using local database (OK for dev)")

            # Check Ollama URL
            if not settings.ollama_url:
                errors.append("OLLAMA_URL not set")

            # Check vault path
            from pathlib import Path

            vault = Path(settings.vault_path)
            if not vault.exists():
                warnings.append(f"Vault path does not exist: {settings.vault_path}")

            # Pool settings
            if settings.db_pool_max < settings.db_pool_min:
                errors.append("db_pool_max must be >= db_pool_min")

        except Exception as e:
            errors.append(f"Configuration load failed: {e}")

        # Print results
        if errors:
            for err in errors:
                console.print(f"[red]✗ ERROR: {err}[/red]")

        if warnings:
            for warn in warnings:
                console.print(f"[yellow]⚠ WARNING: {warn}[/yellow]")

        if not errors and not warnings:
            console.print("[green]✓ Configuration is valid![/green]")
        elif not errors:
            console.print()
            console.print("[green]✓ Configuration is valid (with warnings)[/green]")
        else:
            console.print()
            console.print("[red]✗ Configuration has errors[/red]")
            raise typer.Exit(1)
        return

    settings = get_settings()

    console.print()
    console.print("[bold cyan]Current Configuration[/bold cyan]")
    console.print()

    table = Table(show_header=False, box=None)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    # Database
    table.add_row("Database URL", mask_database_url(settings.database_url))
    table.add_row("DB Pool", f"{settings.db_pool_min}-{settings.db_pool_max}")

    # Ollama
    table.add_row("Ollama URL", settings.ollama_url)
    table.add_row("Embedding Model", settings.embedding_model)
    table.add_row("Rerank Model", settings.rerank_model)

    # Obsidian
    table.add_row("Vault Path", settings.vault_path)
    table.add_row("Knowledge Folder", settings.knowledge_folder)

    # Search
    table.add_row("RRF k", str(settings.rrf_k))
    table.add_row("Search Limit", str(settings.search_default_limit))
    table.add_row("BM25 Candidates", str(settings.bm25_candidates))
    table.add_row("Vector Candidates", str(settings.vector_candidates))

    if show_all:
        # Show all settings
        console.print()
        console.print("[bold]Additional Settings:[/bold]")
        table.add_row("Rate Limit Enabled", str(settings.rate_limit_enabled))
        table.add_row("Rate Limit Requests", str(settings.rate_limit_requests))
        table.add_row("Require API Key", str(settings.require_api_key))
        table.add_row("Log Format", settings.log_format)
        table.add_row("Log Level", settings.log_level)

    console.print(table)


@app.command()
def doctor() -> None:
    """Run diagnostics on all KAS components."""

    async def _doctor():
        console.print()
        console.print("[bold cyan]KAS Diagnostics[/bold cyan]")
        console.print()

        checks: list[tuple[str, bool, str]] = []

        # Check 1: Configuration
        try:
            settings = get_settings()
            checks.append(("Configuration", True, "Loaded successfully"))
        except Exception as e:
            checks.append(("Configuration", False, str(e)[:60]))

        # Check 2: PostgreSQL
        try:
            db = await get_db()
            db_health = await db.check_health()
            if db_health["status"] == "healthy":
                checks.append((
                    "PostgreSQL",
                    True,
                    f"{db_health.get('content_count', 0)} items, {db_health.get('chunk_count', 0)} chunks",
                ))
            else:
                checks.append(("PostgreSQL", False, db_health.get("error", "Unhealthy")))
        except Exception as e:
            checks.append(("PostgreSQL", False, str(e)[:60]))

        # Check 3: Ollama
        try:
            ollama_status = await check_ollama_health()
            if ollama_status.healthy:
                checks.append((
                    "Ollama",
                    True,
                    f"{len(ollama_status.models_loaded)} models loaded",
                ))
            else:
                checks.append(("Ollama", False, ollama_status.error or "Not healthy"))
        except Exception as e:
            checks.append(("Ollama", False, str(e)[:60]))

        # Check 4: Embedding Model
        try:
            settings = get_settings()
            ollama_status = await check_ollama_health()
            # Check if embedding model is loaded (handle :latest suffix)
            model_name = settings.embedding_model
            model_loaded = any(
                m.startswith(model_name) or model_name in m
                for m in ollama_status.models_loaded
            )
            if model_loaded:
                checks.append(("Embedding Model", True, model_name))
            else:
                checks.append((
                    "Embedding Model",
                    False,
                    f"{model_name} not loaded. Run: ollama pull {model_name}",
                ))
        except Exception as e:
            checks.append(("Embedding Model", False, str(e)[:60]))

        # Check 5: Vault Path
        try:
            from pathlib import Path

            settings = get_settings()
            vault = Path(settings.vault_path)
            if vault.exists():
                file_count = len(list(vault.rglob("*.md")))
                checks.append(("Obsidian Vault", True, f"{file_count} markdown files"))
            else:
                checks.append(("Obsidian Vault", False, "Path does not exist"))
        except Exception as e:
            checks.append(("Obsidian Vault", False, str(e)[:60]))

        # Check 6: API Server
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8000/health", timeout=5.0)
                if response.status_code == 200:
                    checks.append(("API Server", True, "Running on port 8000"))
                else:
                    checks.append(("API Server", False, f"Status {response.status_code}"))
        except Exception:
            checks.append(("API Server", False, "Not running"))

        # Display results
        all_ok = True
        for name, ok, details in checks:
            status = "[green]✓[/green]" if ok else "[red]✗[/red]"
            status_text = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
            console.print(f"{status} {name}: {status_text}")
            console.print(f"  [dim]{details}[/dim]")
            if not ok:
                all_ok = False

        console.print()
        if all_ok:
            console.print("[bold green]All checks passed![/bold green]")
        else:
            console.print("[bold yellow]Some checks failed. Review above for details.[/bold yellow]")
            raise typer.Exit(1)

        await close_db()
        await close_embedding_service()

    run_async(_doctor())


@app.command()
def maintenance(
    vacuum: Annotated[bool, typer.Option("--vacuum", help="Run VACUUM ANALYZE on database")] = False,
    reindex: Annotated[bool, typer.Option("--reindex", help="Rebuild search indexes")] = False,
    cleanup: Annotated[bool, typer.Option("--cleanup", help="Clean up orphaned chunks")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show what would be done")] = False,
) -> None:
    """Database maintenance tasks."""
    if not any([vacuum, reindex, cleanup]):
        console.print("[yellow]Specify at least one maintenance task:[/yellow]")
        console.print("  --vacuum   Run VACUUM ANALYZE")
        console.print("  --reindex  Rebuild search indexes")
        console.print("  --cleanup  Clean up orphaned chunks")
        raise typer.Exit(1)

    async def _maintenance():
        try:
            db = await get_db()

            if vacuum:
                console.print("[bold]Running VACUUM ANALYZE...[/bold]")
                if dry_run:
                    console.print("[dim]Would run: VACUUM ANALYZE[/dim]")
                else:
                    async with db._pool.acquire() as conn:
                        await conn.execute("VACUUM ANALYZE")
                    console.print("[green]✓[/green] VACUUM ANALYZE complete")

            if reindex:
                console.print("[bold]Rebuilding indexes...[/bold]")
                indexes = [
                    "idx_chunks_content_id",
                    "idx_content_namespace",
                    "idx_content_type",
                ]
                for idx in indexes:
                    if dry_run:
                        console.print(f"[dim]Would run: REINDEX INDEX {idx}[/dim]")
                    else:
                        try:
                            async with db._pool.acquire() as conn:
                                await conn.execute(f"REINDEX INDEX {idx}")
                            console.print(f"[green]✓[/green] Reindexed {idx}")
                        except Exception as e:
                            console.print(f"[yellow]⚠[/yellow] {idx}: {e}")

            if cleanup:
                console.print("[bold]Cleaning up orphaned chunks...[/bold]")
                if dry_run:
                    async with db._pool.acquire() as conn:
                        orphaned = await conn.fetchval("""
                            SELECT COUNT(*) FROM chunks c
                            LEFT JOIN content ct ON c.content_id = ct.id
                            WHERE ct.id IS NULL
                        """)
                    console.print(f"[dim]Would delete {orphaned} orphaned chunks[/dim]")
                else:
                    async with db._pool.acquire() as conn:
                        result = await conn.execute("""
                            DELETE FROM chunks c
                            USING (
                                SELECT c.id FROM chunks c
                                LEFT JOIN content ct ON c.content_id = ct.id
                                WHERE ct.id IS NULL
                            ) orphans
                            WHERE c.id = orphans.id
                        """)
                        # Parse the result to get count
                        count = result.split()[-1] if result else "0"
                    console.print(f"[green]✓[/green] Deleted {count} orphaned chunks")

            console.print()
            console.print("[bold green]Maintenance complete![/bold green]")

        finally:
            await close_db()

    run_async(_maintenance())


@app.command("export")
def export_cmd(
    output: Annotated[str, typer.Option("--output", "-o", help="Output file path")] = "kas-export.json",
    format: Annotated[str, typer.Option("--format", "-f", help="Format: json, jsonl")] = "json",
    namespace: Annotated[str | None, typer.Option("--namespace", "-ns", help="Filter by namespace")] = None,
    include_embeddings: Annotated[bool, typer.Option("--embeddings", help="Include embedding vectors")] = False,
) -> None:
    """Export knowledge base content."""
    import httpx

    console.print(f"[bold]Exporting to {output}...[/bold]")

    try:
        with httpx.Client(timeout=300.0) as client:
            response = client.post(
                "http://localhost:8000/api/v1/export",
                json={
                    "format": format,
                    "namespace": namespace,
                    "include_chunks": True,
                    "include_embeddings": include_embeddings,
                },
            )

            if response.status_code != 200:
                console.print(f"[red]Export failed: {response.text}[/red]")
                raise typer.Exit(1)

            with open(output, "wb") as f:
                f.write(response.content)

        console.print(f"[green]✓[/green] Exported to {output}")

    except httpx.RequestError as e:
        console.print(f"[red]API not available: {e}[/red]")
        console.print("[dim]Make sure the KAS API is running[/dim]")
        raise typer.Exit(1)


@app.command("import")
def import_cmd(
    input_file: Annotated[str, typer.Argument(help="Input file path")],
    skip_existing: Annotated[bool, typer.Option("--skip-existing", help="Skip existing items")] = True,
) -> None:
    """Import content from backup file."""
    import httpx
    from pathlib import Path

    path = Path(input_file)
    if not path.exists():
        console.print(f"[red]File not found: {input_file}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Importing from {input_file}...[/bold]")

    try:
        with httpx.Client(timeout=300.0) as client:
            with open(path, "rb") as f:
                files = {"file": (path.name, f, "application/json")}
                response = client.post(
                    "http://localhost:8000/api/v1/export/import",
                    files=files,
                    params={"skip_existing": skip_existing},
                )

            if response.status_code != 200:
                console.print(f"[red]Import failed: {response.text}[/red]")
                raise typer.Exit(1)

            result = response.json()

        console.print(f"[green]✓[/green] Import complete")
        console.print(f"  Total: {result['total']}")
        console.print(f"  Imported: {result['imported']}")
        console.print(f"  Skipped: {result['skipped']}")
        if result.get("errors"):
            console.print(f"  [yellow]Errors: {len(result['errors'])}[/yellow]")

    except httpx.RequestError as e:
        console.print(f"[red]API not available: {e}[/red]")
        console.print("[dim]Make sure the KAS API is running[/dim]")
        raise typer.Exit(1)


# =============================================================================
# Ingest Commands
# =============================================================================

ingest_app = typer.Typer(help="Ingest content into the knowledge base")
app.add_typer(ingest_app, name="ingest")


@ingest_app.command("youtube")
def ingest_youtube_cmd(
    video: Annotated[str, typer.Argument(help="YouTube URL or video ID")],
    title: Annotated[str | None, typer.Option("--title", "-t", help="Override title")] = None,
    tags: Annotated[list[str] | None, typer.Option("--tag", "-T", help="Tags to add")] = None,
) -> None:
    """Ingest a YouTube video transcript."""
    from knowledge.ingest.youtube import ingest_youtube

    async def _ingest():
        try:
            # Check Ollama first
            ollama_status = await check_ollama_health()
            if not ollama_status.healthy:
                console.print(f"[red]Ollama not available: {ollama_status.error}[/red]")
                console.print("[dim]Ollama is required for generating embeddings[/dim]")
                raise typer.Exit(1)

            with console.status("[bold blue]Ingesting YouTube video..."):
                result = await ingest_youtube(video, title=title, tags=tags)

            if result.success:
                console.print(f"[green]✓[/green] {result.message}")
                console.print(f"  File: {result.filepath}")
            else:
                console.print(f"[red]✗[/red] {result.error}")
                raise typer.Exit(1)

        finally:
            await close_db()
            await close_embedding_service()

    run_async(_ingest())


@ingest_app.command("bookmark")
def ingest_bookmark_cmd(
    url: Annotated[str, typer.Argument(help="URL to ingest")],
    title: Annotated[str | None, typer.Option("--title", "-t", help="Override title")] = None,
    tags: Annotated[list[str] | None, typer.Option("--tag", "-T", help="Tags to add")] = None,
) -> None:
    """Ingest a web page/bookmark."""
    from knowledge.ingest.bookmark import ingest_bookmark

    async def _ingest():
        try:
            # Check Ollama first
            ollama_status = await check_ollama_health()
            if not ollama_status.healthy:
                console.print(f"[red]Ollama not available: {ollama_status.error}[/red]")
                console.print("[dim]Ollama is required for generating embeddings[/dim]")
                raise typer.Exit(1)

            with console.status("[bold blue]Ingesting bookmark..."):
                result = await ingest_bookmark(url, title=title, tags=tags)

            if result.success:
                console.print(f"[green]✓[/green] {result.message}")
                console.print(f"  File: {result.filepath}")
                if result.error:  # Warning
                    console.print(f"  [yellow]{result.error}[/yellow]")
            else:
                console.print(f"[red]✗[/red] {result.error}")
                raise typer.Exit(1)

        finally:
            await close_db()
            await close_embedding_service()

    run_async(_ingest())


@ingest_app.command("file")
def ingest_file_cmd(
    path: Annotated[str, typer.Argument(help="Path to file (PDF, TXT, MD)")],
    title: Annotated[str | None, typer.Option("--title", "-t", help="Override title")] = None,
    tags: Annotated[list[str] | None, typer.Option("--tag", "-T", help="Tags to add")] = None,
) -> None:
    """Ingest a local file (PDF, TXT, MD)."""
    from knowledge.ingest.files import ingest_file

    async def _ingest():
        try:
            # Check Ollama first
            ollama_status = await check_ollama_health()
            if not ollama_status.healthy:
                console.print(f"[red]Ollama not available: {ollama_status.error}[/red]")
                console.print("[dim]Ollama is required for generating embeddings[/dim]")
                raise typer.Exit(1)

            with console.status("[bold blue]Ingesting file..."):
                result = await ingest_file(path, title=title, tags=tags)

            if result.success:
                console.print(f"[green]✓[/green] {result.message}")
                console.print(f"  File: {result.filepath}")
            else:
                console.print(f"[red]✗[/red] {result.error}")
                raise typer.Exit(1)

        finally:
            await close_db()
            await close_embedding_service()

    run_async(_ingest())


@ingest_app.command("directory")
def ingest_directory_cmd(
    path: Annotated[str, typer.Argument(help="Directory to scan")],
    recursive: Annotated[
        bool, typer.Option("--recursive", "-r", help="Scan subdirectories")
    ] = False,
    tags: Annotated[list[str] | None, typer.Option("--tag", "-T", help="Tags to add")] = None,
) -> None:
    """Ingest all supported files from a directory."""
    from knowledge.ingest.files import ingest_file, scan_directory

    async def _ingest():
        try:
            # Check Ollama first
            ollama_status = await check_ollama_health()
            if not ollama_status.healthy:
                console.print(f"[red]Ollama not available: {ollama_status.error}[/red]")
                console.print("[dim]Ollama is required for generating embeddings[/dim]")
                raise typer.Exit(1)

            # Scan directory
            files = scan_directory(path, recursive=recursive)
            if not files:
                console.print(f"[yellow]No supported files found in: {path}[/yellow]")
                return

            console.print(f"Found {len(files)} files to ingest")

            # Ingest each file
            success_count = 0
            for file_path in files:
                with console.status(f"[bold blue]Ingesting {file_path.name}..."):
                    result = await ingest_file(file_path, tags=tags)

                if result.success:
                    console.print(f"[green]✓[/green] {result.title}")
                    success_count += 1
                else:
                    console.print(f"[red]✗[/red] {file_path.name}: {result.error}")

            console.print()
            console.print(f"Ingested {success_count}/{len(files)} files")

        finally:
            await close_db()
            await close_embedding_service()

    run_async(_ingest())


# =============================================================================
# Review Commands
# =============================================================================

review_app = typer.Typer(help="Manage spaced repetition review queue")
app.add_typer(review_app, name="review")


@review_app.command("due")
def review_due_cmd(
    limit: Annotated[int, typer.Option("--limit", "-n", help="Maximum items to show")] = 20,
) -> None:
    """Show items due for review."""
    from knowledge.review import get_due_items, get_review_stats_simple

    async def _due():
        try:
            stats = await get_review_stats_simple()
            items = await get_due_items(limit=limit)

            console.print()
            console.print("[bold cyan]Review Queue Status[/bold cyan]")
            console.print()

            # Stats summary
            summary = Table(show_header=False, box=None)
            summary.add_column("Metric", style="cyan")
            summary.add_column("Value", style="green", justify="right")

            summary.add_row("Due Now", str(stats["due_now"]))
            summary.add_row("New", str(stats["new"]))
            summary.add_row("Learning", str(stats["learning"]))
            summary.add_row("Review", str(stats["review"]))
            summary.add_row("Total Active", str(stats["total_active"]))

            console.print(summary)
            console.print()

            if not items:
                console.print("[green]No items due for review![/green]")
                return

            # Due items table
            table = Table(title=f"Due Items ({len(items)})")
            table.add_column("Type", style="magenta", width=10)
            table.add_column("Title", style="green")
            table.add_column("State", style="cyan", width=12)
            table.add_column("Reps", justify="right", width=6)

            for item in items:
                state_name = (
                    "New" if item.is_new else ("Learning" if item.is_learning else "Review")
                )
                table.add_row(
                    item.content_type,
                    item.title[:50] + "..." if len(item.title) > 50 else item.title,
                    state_name,
                    str(item.reps),
                )

            console.print(table)

        finally:
            await close_db()

    run_async(_due())


@review_app.command("stats")
def review_stats_cmd() -> None:
    """Show detailed review statistics."""
    from knowledge.review import get_review_stats

    async def _stats():
        try:
            stats = await get_review_stats()

            console.print()
            console.print("[bold cyan]Review Statistics[/bold cyan]")
            console.print()

            # Main stats table
            table = Table(show_header=False, box=None)
            table.add_column("Metric", style="cyan", width=25)
            table.add_column("Value", style="green", justify="right")

            table.add_row("Total Active Items", str(stats.total_active))
            table.add_row("Due Now", str(stats.due_now))
            table.add_row("Suspended", str(stats.suspended_count))
            table.add_row("", "")  # Spacer

            table.add_row("[bold]By State[/bold]", "")
            table.add_row("  New (never reviewed)", str(stats.new_count))
            table.add_row("  Learning", str(stats.learning_count))
            table.add_row("  Review", str(stats.review_count))
            table.add_row("", "")  # Spacer

            table.add_row("[bold]Averages[/bold]", "")
            if stats.average_stability is not None:
                table.add_row("  Stability", f"{stats.average_stability:.2f}")
            else:
                table.add_row("  Stability", "N/A")

            if stats.average_difficulty is not None:
                table.add_row("  Difficulty", f"{stats.average_difficulty:.2f}")
            else:
                table.add_row("  Difficulty", "N/A")

            table.add_row("", "")  # Spacer
            table.add_row("[bold]Today[/bold]", "")
            table.add_row("  Reviews Completed", str(stats.reviews_today))

            console.print(table)
            console.print()

            # Progress bar for due items
            if stats.total_active > 0:
                pct_due = (stats.due_now / stats.total_active) * 100
                console.print(f"[dim]Queue progress: {stats.due_now}/{stats.total_active} due ({pct_due:.1f}%)[/dim]")

        finally:
            await close_db()

    run_async(_stats())


@review_app.command("start")
def review_start_cmd(
    limit: Annotated[int, typer.Option("--limit", "-n", help="Maximum items to review")] = 10,
) -> None:
    """Start an interactive review session."""
    from knowledge.review import ReviewRating, get_due_items, get_review_engine, submit_review

    async def _start():
        try:
            items = await get_due_items(limit=limit)

            if not items:
                console.print("[green]No items due for review![/green]")
                return

            console.print(f"\n[bold]Starting review session with {len(items)} items[/bold]\n")
            console.print("[dim]Rating keys: 1=Again, 2=Hard, 3=Good, 4=Easy, q=Quit[/dim]\n")

            engine = get_review_engine()
            reviewed = 0

            for i, item in enumerate(items, 1):
                # Show item
                console.print(f"\n[bold cyan]Item {i}/{len(items)}[/bold cyan]")
                console.print(f"[bold]{item.title}[/bold] [{item.content_type}]")
                console.print()

                if item.preview_text:
                    preview = item.preview_text[:500]
                    if len(item.preview_text) > 500:
                        preview += "..."
                    console.print(
                        Panel(
                            preview,
                            title="Preview",
                            border_style="blue",
                        )
                    )

                # Show intervals
                intervals = engine.get_next_intervals(
                    {
                        "state": item.state.value,
                        "stability": item.stability,
                        "difficulty": item.difficulty,
                        "reps": item.reps,
                        "lapses": item.lapses,
                    }
                )

                console.print("\n[dim]Next review if rated:[/dim]")
                for rating, due in intervals.items():
                    delta = due - datetime.now(UTC)
                    if delta.days > 0:
                        time_str = f"{delta.days}d"
                    elif delta.seconds > 3600:
                        time_str = f"{delta.seconds // 3600}h"
                    else:
                        time_str = f"{delta.seconds // 60}m"
                    console.print(f"  {rating.value}: {time_str}")

                # Get rating
                while True:
                    response = (
                        console.input("\n[bold]Rate (1-4, q to quit):[/bold] ").strip().lower()
                    )

                    if response == "q":
                        console.print(
                            f"\n[yellow]Session ended. Reviewed {reviewed}/{len(items)} items.[/yellow]"
                        )
                        return

                    rating_map = {
                        "1": ReviewRating.AGAIN,
                        "2": ReviewRating.HARD,
                        "3": ReviewRating.GOOD,
                        "4": ReviewRating.EASY,
                    }

                    if response in rating_map:
                        rating = rating_map[response]
                        result = await submit_review(item.content_id, rating)

                        if result:
                            console.print(
                                f"[green]✓[/green] Rated {rating.value}, next review: {result.new_due.strftime('%Y-%m-%d %H:%M')}"
                            )
                            reviewed += 1
                        else:
                            console.print("[red]Failed to submit review[/red]")
                        break
                    else:
                        console.print("[red]Invalid input. Use 1-4 or q.[/red]")

            console.print(
                f"\n[bold green]Review session complete! Reviewed {reviewed} items.[/bold green]"
            )

        finally:
            await close_db()

    run_async(_start())


@review_app.command("add")
def review_add_cmd(
    content_id: Annotated[str, typer.Argument(help="Content ID to add to review queue")],
) -> None:
    """Add content to the review queue."""
    from uuid import UUID

    from knowledge.review import add_to_review_queue

    async def _add():
        try:
            uuid = UUID(content_id)
            added = await add_to_review_queue(uuid)

            if added:
                console.print("[green]✓[/green] Added to review queue")
            else:
                console.print("[yellow]Already in review queue[/yellow]")

        except ValueError:
            console.print(f"[red]Invalid UUID: {content_id}[/red]")
            raise typer.Exit(1) from None
        finally:
            await close_db()

    run_async(_add())


@review_app.command("suspend")
def review_suspend_cmd(
    content_id: Annotated[str, typer.Argument(help="Content ID to suspend")],
) -> None:
    """Suspend an item from review."""
    from uuid import UUID

    from knowledge.review import suspend_item

    async def _suspend():
        try:
            uuid = UUID(content_id)
            suspended = await suspend_item(uuid)

            if suspended:
                console.print("[green]✓[/green] Suspended from review")
            else:
                console.print("[yellow]Item not found in queue[/yellow]")

        except ValueError:
            console.print(f"[red]Invalid UUID: {content_id}[/red]")
            raise typer.Exit(1) from None
        finally:
            await close_db()

    run_async(_suspend())


# =============================================================================
# Project Commands
# =============================================================================


@app.command()
def context(
    project_path: Annotated[str, typer.Argument(help="Path to project directory")] = ".",
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of context items")] = 5,
    output: Annotated[str, typer.Option("--output", "-o", help="Output format: markdown, json")] = "markdown",
) -> None:
    """
    Generate context from knowledge base for a project.

    Detects project namespace and retrieves relevant knowledge for
    session preloading.
    """
    from pathlib import Path
    import json as json_module
    import httpx

    project = Path(project_path).resolve()

    if not project.exists():
        console.print(f"[red]Directory not found: {project}[/red]")
        raise typer.Exit(1)

    # Detect project name from directory
    project_name = project.name
    namespace = f"projects/{project_name}"

    # Check for CLAUDE.md to extract project context
    claude_md = project / "CLAUDE.md"
    project_description = None
    if claude_md.exists():
        content = claude_md.read_text()
        # Extract first paragraph after # heading
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("# "):
                # Look for description in next non-empty lines
                for j in range(i + 1, min(i + 10, len(lines))):
                    if lines[j].strip() and not lines[j].startswith("#"):
                        project_description = lines[j].strip()
                        break
                break

    console.print(f"[bold]Project:[/bold] {project_name}")
    console.print(f"[bold]Namespace:[/bold] {namespace}")
    if project_description:
        console.print(f"[dim]{project_description}[/dim]")
    console.print()

    # Search for relevant content
    try:
        # Try project namespace first
        response = httpx.get(
            "http://localhost:8000/api/v1/search",
            params={"q": project_name, "namespace": f"{namespace}*", "limit": limit},
            timeout=10.0,
        )
        results = response.json().get("results", [])

        # If no results, try broader search
        if not results:
            response = httpx.get(
                "http://localhost:8000/api/v1/search",
                params={"q": project_name, "limit": limit},
                timeout=10.0,
            )
            results = response.json().get("results", [])

        if not results:
            console.print("[yellow]No relevant context found for this project.[/yellow]")
            console.print(f"[dim]Use kas_capture with namespace='{namespace}' to add knowledge.[/dim]")
            return

        if output == "json":
            console.print(json_module.dumps(results, indent=2))
        else:
            # Markdown output
            console.print(f"## Context for {project_name}\n")
            for i, r in enumerate(results, 1):
                ns = r.get("namespace") or "default"
                title = r.get("title", "Untitled")
                chunk = r.get("chunk_text", "")[:300]
                console.print(f"### {i}. {title}")
                console.print(f"*Namespace: {ns}*\n")
                console.print(f"{chunk}...\n")
                console.print("---\n")

    except httpx.RequestError as e:
        console.print(f"[red]KAS API not available: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def init(
    project_path: Annotated[str, typer.Argument(help="Path to project directory")] = ".",
    force: Annotated[bool, typer.Option("--force", "-f", help="Overwrite existing config")] = False,
) -> None:
    """Initialize KAS integration in a project.

    Creates .claude/mcp_settings.json for MCP server connection.
    """
    from pathlib import Path
    import json
    import shutil

    project = Path(project_path).resolve()

    if not project.exists():
        console.print(f"[red]Directory not found: {project}[/red]")
        raise typer.Exit(1)

    if not project.is_dir():
        console.print(f"[red]Not a directory: {project}[/red]")
        raise typer.Exit(1)

    claude_dir = project / ".claude"
    mcp_settings = claude_dir / "mcp_settings.json"

    # Check for existing config
    if mcp_settings.exists() and not force:
        console.print(f"[yellow]MCP settings already exist: {mcp_settings}[/yellow]")
        console.print("[dim]Use --force to overwrite[/dim]")
        raise typer.Exit(1)

    # Create .claude directory
    claude_dir.mkdir(exist_ok=True)

    # Write MCP settings
    settings = {
        "mcpServers": {
            "kas": {
                "command": "node",
                "args": ["/Users/d/claude-code/personal/knowledge-activation-system/mcp-server/dist/index.js"],
                "env": {
                    "KAS_API_URL": "http://localhost:8000"
                }
            }
        }
    }

    with open(mcp_settings, "w") as f:
        json.dump(settings, f, indent=2)

    console.print(f"[green]✓[/green] Created {mcp_settings}")

    # Copy integration guide if docs folder exists
    docs_dir = project / "docs"
    if docs_dir.exists():
        template_guide = Path("/Users/d/claude-code/templates/kas-project/docs/KAS_INTEGRATION.md")
        if template_guide.exists():
            dest_guide = docs_dir / "KAS_INTEGRATION.md"
            if not dest_guide.exists() or force:
                shutil.copy(template_guide, dest_guide)
                console.print(f"[green]✓[/green] Created {dest_guide}")

    console.print()
    console.print("[bold]KAS integration initialized![/bold]")
    console.print()
    console.print("Next steps:")
    console.print("  1. Start a new Claude Code session in this project")
    console.print("  2. Use kas_search, kas_ask, kas_capture tools")
    console.print()
    console.print("[dim]Available MCP tools:[/dim]")
    console.print("  kas_search   - Search knowledge base")
    console.print("  kas_ask      - Q&A with citations")
    console.print("  kas_capture  - Save new learnings")
    console.print("  kas_stats    - Check KAS health")


if __name__ == "__main__":
    app()
