# Claude Code Setup Instructions
# Run these commands IN CLAUDE CODE (not regular terminal)
# Created: January 10, 2026

## STEP 1: Verify MCP Servers (Auto-configured)
# The following MCP servers have been added to your .claude.json:
# - taskmaster-ai (Task Master AI)
# - context7 (Context7 documentation)
# - playwright (Browser automation)
#
# To verify they're working, run in Claude Code:
claude mcp list

## STEP 2: Install ClaudeKit CLI (Global)
# Run in your regular terminal (not Claude Code):
npm install -g claudekit

# Then in any project, run:
claudekit setup --all

## STEP 3: Install Compound Engineering Plugin
# Run IN Claude Code:
/plugin marketplace add EveryInc/compound-engineering-plugin
/plugin install compound-engineering@compound-engineering-plugin

## STEP 4: Verify Everything
# In Claude Code, type:
/help
# You should see your custom commands: /prd, /status, /checkpoint, /plan, /explain, /ship

## STEP 5: Test Task Master (Optional)
# Navigate to a test project and run:
task-master init
# This creates the .taskmaster folder structure

## Your New Workflow Commands:
# /prd [project-name]     - Start PRD interview workflow
# /status                 - Get project status
# /checkpoint             - Create safe restore point
# /plan [feature]         - Quick implementation plan
# /explain                - Explain what just happened
# /ship                   - Commit, push, create PR

## Context7 Usage:
# Just add "use context7" to any prompt:
# "How do I use React hooks? use context7"

## Task Master Usage:
# "Parse the PRD and set up tasks"
# "What should I work on next?"
# "Mark task 3 complete"

## Your Project Structure:
# ~/claude-code/
# ├── personal/    - Side projects
# ├── finance/     - Finance dashboard
# ├── ai-tools/    - RAG system
# ├── learning/    - Tutorials
# └── templates/   - Reusable starters
