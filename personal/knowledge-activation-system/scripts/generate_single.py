#!/usr/bin/env python3
"""Generate a single article using Ollama - for serial execution."""

import argparse
import asyncio
import re
import sys
from datetime import datetime
from pathlib import Path

import httpx

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:14b"
OBSIDIAN_BASE = Path.home() / "Obsidian" / "Knowledge" / "Notes"

ARTICLE_PROMPT = """Write a comprehensive technical guide about: {title}

Context: {description}

Requirements:
1. Write 800-1200 words of substantive technical content
2. Include practical code examples where relevant
3. Use clear headings and structure
4. Include best practices and common pitfalls
5. Be specific and actionable, not generic
6. Target an intermediate developer audience

Format the response as a complete markdown article with:
- A clear introduction explaining the topic
- Main content with code examples
- Best practices section
- Common mistakes to avoid
- Conclusion with key takeaways

Do NOT include YAML frontmatter - just the article content starting with the main heading."""


def title_to_filename(title: str) -> str:
    """Convert title to a valid filename."""
    filename = re.sub(r'[^\w\s-]', '', title.lower())
    filename = re.sub(r'[\s_]+', '-', filename)
    return filename + ".md"


def create_frontmatter(title: str, namespace: str) -> str:
    """Create YAML frontmatter for the article."""
    return f"""---
title: "{title}"
namespace: {namespace}
tags:
  - {namespace}
  - generated
created: {datetime.now().strftime("%Y-%m-%d")}
type: guide
---

"""


async def generate_article(title: str, description: str, namespace: str, output_dir: Path) -> bool:
    """Generate a single article."""
    filename = title_to_filename(title)
    filepath = output_dir / filename

    if filepath.exists():
        print(f"SKIP (exists): {filename}")
        return False

    print(f"Generating: {title}...")

    prompt = ARTICLE_PROMPT.format(title=title, description=description)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 2000,
                    }
                },
                timeout=180.0,
            )
            response.raise_for_status()
            content = response.json()["response"]

            # Write file
            frontmatter = create_frontmatter(title, namespace)
            filepath.write_text(frontmatter + content)
            print(f"  ✓ Saved: {filename}")
            return True

        except Exception as e:
            print(f"  ✗ Error: {e}")
            return False


async def main():
    parser = argparse.ArgumentParser(description="Generate a single article")
    parser.add_argument("--title", required=True, help="Article title")
    parser.add_argument("--desc", required=True, help="Article description")
    parser.add_argument("--namespace", required=True, help="Content namespace")
    args = parser.parse_args()

    output_dir = OBSIDIAN_BASE / args.namespace
    output_dir.mkdir(parents=True, exist_ok=True)

    success = await generate_article(args.title, args.desc, args.namespace, output_dir)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
