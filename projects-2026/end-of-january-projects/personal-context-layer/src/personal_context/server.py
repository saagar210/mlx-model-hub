"""Unified Personal Context MCP Server using FastMCP."""

import json
from typing import Annotated

from mcp.server.fastmcp import FastMCP

from personal_context.adapters.obsidian import ObsidianAdapter
from personal_context.adapters.git import GitAdapter
from personal_context.adapters.kas import KASAdapter
from personal_context.config import get_settings
from personal_context.utils.fusion import reciprocal_rank_fusion, deduplicate_by_content

# Initialize FastMCP server
mcp = FastMCP(
    "personal-context",
    instructions="Unified access to personal knowledge sources: Obsidian notes, Git history, and KAS knowledge base. Use search_notes for Obsidian, get_git_context for Git, kas_search for knowledge base, search_all for cross-source search.",
)

# Lazy-loaded adapters
_obsidian: ObsidianAdapter | None = None
_git: GitAdapter | None = None
_kas: KASAdapter | None = None


def get_obsidian() -> ObsidianAdapter:
    """Get or create Obsidian adapter."""
    global _obsidian
    if _obsidian is None:
        settings = get_settings()
        _obsidian = ObsidianAdapter(settings.obsidian_vault)
    return _obsidian


def get_git() -> GitAdapter:
    """Get or create Git adapter."""
    global _git
    if _git is None:
        settings = get_settings()
        _git = GitAdapter(settings.git_repos)
    return _git


def get_kas() -> KASAdapter:
    """Get or create KAS adapter."""
    global _kas
    if _kas is None:
        settings = get_settings()
        _kas = KASAdapter(settings.kas_api_url)
    return _kas


# =============================================================================
# OBSIDIAN TOOLS (Granular)
# =============================================================================


@mcp.tool()
async def search_notes(
    query: Annotated[str, "Search query for note content and titles"],
    limit: Annotated[int, "Maximum results to return"] = 10,
) -> str:
    """Search Obsidian notes by content and filename.

    Use this to find notes related to a topic, concept, or keyword.
    Returns matching notes with relevance-ranked snippets.
    """
    adapter = get_obsidian()
    results = await adapter.search(query, limit=limit)

    if not results:
        return f"No notes found matching '{query}'"

    output = [f"Found {len(results)} notes matching '{query}':\n"]
    for item in results:
        output.append(f"- **{item.title}** ({item.path})")
        output.append(f"  Score: {item.relevance_score:.2f}")
        snippet = item.content.replace("\n", " ")[:150]
        output.append(f"  {snippet}...")
        output.append("")

    return "\n".join(output)


@mcp.tool()
async def read_note(
    path: Annotated[str, "Path to note relative to vault (e.g. 'Knowledge/Notes/my-note.md')"],
) -> str:
    """Read the full content of an Obsidian note.

    Use this to get the complete contents of a specific note,
    including its YAML frontmatter and backlinks.
    """
    adapter = get_obsidian()
    result = await adapter.read_note(path)

    if not result:
        return f"Note not found: {path}"

    output = [f"# {result.title}\n"]
    output.append(f"**Path:** {result.path}")
    output.append(f"**Modified:** {result.modified.strftime('%Y-%m-%d %H:%M')}")

    if result.frontmatter:
        output.append(f"**Frontmatter:** {json.dumps(result.frontmatter, default=str)}")

    if result.backlinks:
        output.append(f"**Backlinks:** {', '.join(result.backlinks)}")

    output.append("\n---\n")
    output.append(result.content)

    return "\n".join(output)


@mcp.tool()
async def get_backlinks(
    path: Annotated[str, "Path to note relative to vault"],
) -> str:
    """Find all notes that link to a specific note.

    Use this to discover related notes and context around a topic.
    """
    adapter = get_obsidian()
    backlinks = await adapter.get_backlinks(path)

    if not backlinks:
        return f"No backlinks found for: {path}"

    output = [f"Notes linking to '{path}':\n"]
    for link in backlinks:
        output.append(f"- {link}")

    return "\n".join(output)


@mcp.tool()
async def recent_notes(
    hours: Annotated[int, "How many hours back to look"] = 24,
    limit: Annotated[int, "Maximum notes to return"] = 10,
) -> str:
    """Get recently modified Obsidian notes.

    Use this to see what notes have been updated recently,
    useful for understanding current working context.
    """
    adapter = get_obsidian()
    results = await adapter.get_recent(hours=hours, limit=limit)

    if not results:
        return f"No notes modified in the last {hours} hours"

    output = [f"Notes modified in last {hours} hours:\n"]
    for item in results:
        time_str = item.timestamp.strftime("%Y-%m-%d %H:%M")
        output.append(f"- **{item.title}** ({item.path})")
        output.append(f"  Modified: {time_str}")
        output.append("")

    return "\n".join(output)


@mcp.tool()
async def notes_by_tag(
    tag: Annotated[str, "Tag to search for (with or without #)"],
    limit: Annotated[int, "Maximum notes to return"] = 20,
) -> str:
    """Find Obsidian notes with a specific tag.

    Use this to find all notes tagged with a particular topic or category.
    """
    adapter = get_obsidian()
    results = await adapter.list_by_tag(tag, limit=limit)

    if not results:
        return f"No notes found with tag: {tag}"

    output = [f"Notes with tag '#{tag.lstrip('#')}':\n"]
    for item in results:
        output.append(f"- **{item.title}** ({item.path})")

    return "\n".join(output)


# =============================================================================
# GIT TOOLS (Granular)
# =============================================================================


@mcp.tool()
async def get_git_context(
    repo: Annotated[str | None, "Repository name/path (default: auto-detect)"] = None,
) -> str:
    """Get current Git context: branch, status, recent commits.

    Use this to understand the current state of a git repository,
    including what branch you're on and recent activity.
    """
    adapter = get_git()
    context = await adapter.get_repo_context(repo)

    output = [f"# Git Context: {context['repo']}\n"]
    output.append(f"**Branch:** {context['branch']}")
    output.append(f"**Status:** {context['status']}")
    output.append("\n**Recent Commits:**")

    for commit in context["recent_commits"]:
        output.append(f"- `{commit['hash']}` {commit['message']}")
        output.append(f"  {commit['date']} by {commit['author']}")

    return "\n".join(output)


@mcp.tool()
async def search_commits(
    query: Annotated[str, "Search query for commit messages"],
    repo: Annotated[str | None, "Repository name (default: all repos)"] = None,
    limit: Annotated[int, "Maximum commits to return"] = 10,
) -> str:
    """Search Git commit messages.

    Use this to find commits related to a feature, bug fix, or topic.
    """
    adapter = get_git()
    results = await adapter.search_commits(query, repo, limit=limit)

    if not results:
        return f"No commits found matching '{query}'"

    output = [f"Found {len(results)} commits matching '{query}':\n"]
    for item in results:
        output.append(f"- **{item.title}**")
        output.append(f"  {item.timestamp.strftime('%Y-%m-%d')} | {item.metadata.get('author', 'unknown')}")
        output.append("")

    return "\n".join(output)


@mcp.tool()
async def file_history(
    file_path: Annotated[str, "Path to file relative to repo"],
    repo: Annotated[str | None, "Repository name (default: auto-detect)"] = None,
    limit: Annotated[int, "Number of commits to show"] = 10,
) -> str:
    """Get commit history for a specific file.

    Use this to understand how a file has evolved over time.
    """
    adapter = get_git()
    history = await adapter.get_file_history(file_path, repo, count=limit)

    if not history:
        return f"No history found for: {file_path}"

    output = [f"History for {file_path}:\n"]
    for commit in history:
        output.append(f"- `{commit['hash']}` {commit['message']}")
        output.append(f"  {commit['date']} by {commit['author']}")

    return "\n".join(output)


@mcp.tool()
async def recent_commits(
    hours: Annotated[int, "How many hours back to look"] = 24,
    limit: Annotated[int, "Maximum commits to return"] = 20,
) -> str:
    """Get recent commits across all repositories.

    Use this to see what code changes have been made recently.
    """
    adapter = get_git()
    results = await adapter.get_recent(hours=hours, limit=limit)

    if not results:
        return f"No commits in the last {hours} hours"

    output = [f"Commits in last {hours} hours:\n"]
    for item in results:
        time_str = item.timestamp.strftime("%Y-%m-%d %H:%M")
        output.append(f"- [{time_str}] **{item.title}**")
        output.append(f"  {item.metadata.get('author', 'unknown')}")
        output.append("")

    return "\n".join(output)


@mcp.tool()
async def git_diff(
    repo: Annotated[str | None, "Repository name (default: auto-detect)"] = None,
    staged: Annotated[bool, "Show only staged changes"] = False,
) -> str:
    """Get summary of current uncommitted changes.

    Use this to see what files have been modified.
    """
    adapter = get_git()
    diff = await adapter.get_diff_summary(repo, staged=staged)

    status = "staged" if staged else "all"
    return f"**Changes ({status}):**\n```\n{diff}\n```"


# =============================================================================
# KAS TOOLS (Granular)
# =============================================================================


@mcp.tool()
async def kas_search(
    query: Annotated[str, "Search query for knowledge base"],
    limit: Annotated[int, "Maximum results to return"] = 10,
    namespace: Annotated[str | None, "Namespace/category to search in"] = None,
) -> str:
    """Search the Knowledge Activation System (KAS) knowledge base.

    Use this to find knowledge articles, documentation, and support content.
    KAS contains 1000+ indexed items from various sources.
    """
    adapter = get_kas()

    if not await adapter.health_check():
        return "KAS service is not available. Make sure it's running at localhost:8000"

    if namespace:
        results = await adapter.search_in_namespace(query, namespace, limit=limit)
    else:
        results = await adapter.search(query, limit=limit)

    if not results:
        return f"No knowledge items found matching '{query}'"

    output = [f"Found {len(results)} knowledge items matching '{query}':\n"]
    for item in results:
        output.append(f"- **{item.title}**")
        if item.metadata.get("namespace"):
            output.append(f"  Namespace: {item.metadata['namespace']}")
        if item.metadata.get("score"):
            output.append(f"  Score: {item.metadata['score']:.2f}")
        snippet = item.content.replace("\n", " ")[:150]
        output.append(f"  {snippet}...")
        output.append("")

    return "\n".join(output)


@mcp.tool()
async def kas_ask(
    question: Annotated[str, "Question to ask the knowledge base"],
) -> str:
    """Ask a question using KAS Q&A capability.

    Uses the knowledge base to find and synthesize an answer
    with confidence score and source references.
    """
    adapter = get_kas()

    if not await adapter.health_check():
        return "KAS service is not available. Make sure it's running at localhost:8000"

    result = await adapter.ask(question)

    if not result.get("answer"):
        return f"Could not find an answer for: {question}"

    output = [f"**Question:** {question}\n"]
    output.append(f"**Answer:** {result['answer']}")

    if result.get("confidence"):
        confidence = result["confidence"]
        confidence_label = "High" if confidence > 0.8 else "Medium" if confidence > 0.5 else "Low"
        output.append(f"\n**Confidence:** {confidence_label} ({confidence:.2f})")

    if result.get("sources"):
        output.append("\n**Sources:**")
        for src in result["sources"][:5]:
            output.append(f"- {src}")

    return "\n".join(output)


@mcp.tool()
async def kas_namespaces() -> str:
    """List available KAS namespaces/categories.

    Use this to see what knowledge domains are indexed.
    """
    adapter = get_kas()

    if not await adapter.health_check():
        return "KAS service is not available. Make sure it's running at localhost:8000"

    namespaces = await adapter.get_namespaces()

    if not namespaces:
        return "No namespaces found or endpoint not available"

    output = ["**Available KAS Namespaces:**\n"]
    for ns in namespaces:
        output.append(f"- {ns}")

    return "\n".join(output)


# =============================================================================
# AGGREGATE TOOLS (Cross-source)
# =============================================================================


@mcp.tool()
async def search_all(
    query: Annotated[str, "Search query"],
    sources: Annotated[
        list[str] | None, "Sources to search: obsidian, git, kas (default: all available)"
    ] = None,
    limit: Annotated[int, "Maximum results per source"] = 5,
) -> str:
    """Search across all personal knowledge sources.

    Queries Obsidian notes, Git commits, and KAS knowledge base.
    Results are ranked by relevance and fused across sources using RRF.
    """
    sources = sources or ["obsidian", "git", "kas"]
    results_by_source: list[list] = []
    searched: list[str] = []

    if "obsidian" in sources:
        try:
            adapter = get_obsidian()
            results = await adapter.search(query, limit=limit)
            results_by_source.append(results)
            searched.append("obsidian")
        except Exception:
            pass

    if "git" in sources:
        try:
            adapter = get_git()
            results = await adapter.search(query, limit=limit)
            results_by_source.append(results)
            searched.append("git")
        except Exception:
            pass

    if "kas" in sources:
        try:
            adapter = get_kas()
            if await adapter.health_check():
                results = await adapter.search(query, limit=limit)
                results_by_source.append(results)
                searched.append("kas")
        except Exception:
            pass

    if not results_by_source:
        return f"No results found for '{query}'"

    # Fuse results using RRF
    fused = reciprocal_rank_fusion(results_by_source)
    fused = deduplicate_by_content(fused)[:limit * 2]

    output = [f"Found {len(fused)} results for '{query}' (sources: {', '.join(searched)}):\n"]
    for item in fused:
        output.append(item.to_display())
        output.append("")

    return "\n".join(output)


@mcp.tool()
async def get_recent_activity(
    hours: Annotated[int, "How many hours back to look"] = 24,
    sources: Annotated[
        list[str] | None, "Sources to check: obsidian, git, kas (default: all)"
    ] = None,
) -> str:
    """Get recent activity across all sources.

    Shows a timeline of recently modified notes, commits, and knowledge items.
    """
    sources = sources or ["obsidian", "git", "kas"]
    all_results = []
    searched: list[str] = []

    if "obsidian" in sources:
        try:
            adapter = get_obsidian()
            results = await adapter.get_recent(hours=hours, limit=20)
            all_results.extend(results)
            searched.append("obsidian")
        except Exception:
            pass

    if "git" in sources:
        try:
            adapter = get_git()
            results = await adapter.get_recent(hours=hours, limit=20)
            all_results.extend(results)
            searched.append("git")
        except Exception:
            pass

    if "kas" in sources:
        try:
            adapter = get_kas()
            if await adapter.health_check():
                results = await adapter.get_recent(hours=hours, limit=20)
                all_results.extend(results)
                searched.append("kas")
        except Exception:
            pass

    # Sort by timestamp
    all_results.sort(key=lambda x: x.timestamp, reverse=True)

    if not all_results:
        return f"No activity in the last {hours} hours"

    source_icons = {"obsidian": "📝", "git": "🔀", "kas": "📚"}
    output = [f"Activity in last {hours} hours (sources: {', '.join(searched)}):\n"]
    for item in all_results[:30]:  # Limit total output
        time_str = item.timestamp.strftime("%Y-%m-%d %H:%M")
        icon = source_icons.get(item.source.value, "📄")
        output.append(f"[{time_str}] {icon} **{item.title}**")
        if item.path:
            output.append(f"  {item.path}")
        output.append("")

    return "\n".join(output)


@mcp.tool()
async def get_working_context() -> str:
    """Get current working context snapshot.

    Combines recent notes, current git status, and uncommitted changes
    to provide a comprehensive view of what you're currently working on.
    """
    output = ["# Current Working Context\n"]

    # Git context
    try:
        git = get_git()
        context = await git.get_repo_context()
        output.append("## Git Status")
        output.append(f"**Repo:** {context['repo']} | **Branch:** {context['branch']}")
        if context['status'] != 'clean':
            output.append(f"**Uncommitted changes:**\n```\n{context['status']}\n```")
        output.append("\n**Recent commits:**")
        for c in context['recent_commits'][:3]:
            output.append(f"- `{c['hash']}` {c['message']}")
        output.append("")
    except Exception as e:
        output.append(f"## Git Status\nUnavailable: {e}\n")

    # Recent notes
    try:
        obsidian = get_obsidian()
        recent = await obsidian.get_recent(hours=48, limit=5)
        output.append("## Recent Notes (48h)")
        for note in recent:
            output.append(f"- **{note.title}** ({note.path})")
            output.append(f"  Modified: {note.timestamp.strftime('%Y-%m-%d %H:%M')}")
        output.append("")
    except Exception as e:
        output.append(f"## Recent Notes\nUnavailable: {e}\n")

    return "\n".join(output)


@mcp.tool()
async def get_entity_context(
    entity: Annotated[str, "Entity name to search for (e.g., 'OAuth', 'knowledge-engine')"],
    limit: Annotated[int, "Maximum items per source"] = 5,
) -> str:
    """Get all context related to a specific entity across all sources.

    Searches for mentions of an entity (technology, project, concept) across
    Obsidian notes, Git commits, and KAS knowledge base. Useful for understanding
    everything known about a particular topic.
    """
    from personal_context.utils.entities import find_entity_mentions, extract_entities_from_items

    all_items: list = []
    sources_searched: list[str] = []

    # Search Obsidian
    try:
        obsidian = get_obsidian()
        results = await obsidian.search(entity, limit=limit * 2)
        all_items.extend(results)
        sources_searched.append("obsidian")
    except Exception:
        pass

    # Search Git
    try:
        git = get_git()
        results = await git.search(entity, limit=limit * 2)
        all_items.extend(results)
        sources_searched.append("git")
    except Exception:
        pass

    # Search KAS
    try:
        kas = get_kas()
        if await kas.health_check():
            results = await kas.search(entity, limit=limit * 2)
            all_items.extend(results)
            sources_searched.append("kas")
    except Exception:
        pass

    if not all_items:
        return f"No context found for entity: {entity}"

    # Find items that actually mention the entity
    mentions = find_entity_mentions(entity, all_items, fuzzy=True)

    # Extract related entities from the mentions
    entities = extract_entities_from_items(mentions)

    # Build output
    output = [f"# Context for: {entity}\n"]
    output.append(f"**Sources searched:** {', '.join(sources_searched)}")
    output.append(f"**Total mentions:** {len(mentions)}\n")

    # Group by source
    source_icons = {"obsidian": "📝", "git": "🔀", "kas": "📚"}
    by_source: dict[str, list] = {}
    for item in mentions:
        src = item.source.value
        if src not in by_source:
            by_source[src] = []
        by_source[src].append(item)

    for source, items in by_source.items():
        icon = source_icons.get(source, "📄")
        output.append(f"\n## {icon} {source.title()} ({len(items)} items)\n")
        for item in items[:limit]:
            output.append(f"- **{item.title}**")
            if item.path:
                output.append(f"  Path: {item.path}")
            snippet = item.content.replace("\n", " ")[:100]
            output.append(f"  {snippet}...")
            output.append("")

    # Show related entities
    if entities:
        output.append("\n## Related Entities\n")
        sorted_entities = sorted(
            entities.values(),
            key=lambda e: e.mention_count,
            reverse=True
        )[:10]
        for ent in sorted_entities:
            if ent.name.lower() != entity.lower():
                output.append(f"- **{ent.name}** ({ent.entity_type}) - {ent.mention_count} mentions")

    return "\n".join(output)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
