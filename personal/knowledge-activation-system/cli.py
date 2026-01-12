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
    """Mask password in database URL for display."""
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
    except Exception:
        # Fallback: try to mask any password-like patterns
        import re

        return re.sub(r":([^:@]+)@", ":***@", url)


app = typer.Typer(
    name="knowledge",
    help="Knowledge Activation System - Personal knowledge management with hybrid search.",
    no_args_is_help=True,
)
console = Console()


def run_async(coro):
    """Run async function in sync context."""
    return asyncio.run(coro)


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
                all_healthy = False
        except Exception as e:
            console.print("[red]✗[/red] PostgreSQL: [red]Connection Failed[/red]")
            console.print(f"  Error: {e}")
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
                all_healthy = False
        except Exception as e:
            console.print("[red]✗[/red] Ollama: [red]Connection Failed[/red]")
            console.print(f"  Error: {e}")
            all_healthy = False

        console.print()

        # Overall status
        if all_healthy:
            console.print("[bold green]All services healthy![/bold green]")
        else:
            console.print("[bold red]Some services are unhealthy[/bold red]")
            raise typer.Exit(1)

        await close_db()
        await close_embedding_service()

    run_async(_health())


@app.command()
def config() -> None:
    """Show current configuration."""
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
    table.add_row("Search Limit", str(settings.search_limit))
    table.add_row("BM25 Candidates", str(settings.bm25_candidates))
    table.add_row("Vector Candidates", str(settings.vector_candidates))

    console.print(table)


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


if __name__ == "__main__":
    app()
