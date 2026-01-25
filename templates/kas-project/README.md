# KAS Project Template

A project template pre-configured for Knowledge Activation System integration.

## Usage

### New Project
```bash
# Copy template to new project
cp -r /Users/d/claude-code/templates/kas-project /path/to/new-project
cd /path/to/new-project
```

### Existing Project
```bash
# Initialize KAS in existing project
kas init /path/to/existing-project
```

## What's Included

```
.claude/
  mcp_settings.json    # MCP server config for Claude Code
docs/
  KAS_INTEGRATION.md   # How to use KAS in this project
CLAUDE.md              # Project instructions template
```

## After Setup

1. Start a new Claude Code session in the project
2. MCP tools automatically available: `kas_search`, `kas_ask`, `kas_capture`, `kas_stats`
3. Use `kas_capture` to save learnings as you work
