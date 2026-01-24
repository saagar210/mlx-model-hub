# KAS Integrations Guide

**Last Updated:** 2026-01-20

This document describes all available integrations for the Knowledge Activation System.

---

## Overview

KAS provides multiple integration points to access your knowledge base from various platforms:

| Integration | Purpose | Status |
|-------------|---------|--------|
| MCP Server | Claude Code / Claude Desktop | ✅ Production |
| Web UI | Browser-based interface | ✅ Production |
| CLI | Command-line access | ✅ Production |
| iOS Shortcuts | Mobile automation | ✅ Production |
| Raycast | macOS launcher | ✅ Ready to publish |
| Browser Extension | Chrome/Firefox | ✅ Ready to publish |
| n8n Node | Workflow automation | ✅ Ready to publish |
| Python SDK | Programmatic access | ✅ Production |

---

## 1. MCP Server (Claude Code)

The Model Context Protocol server enables Claude Code and Claude Desktop to interact with KAS.

### Location
```
mcp-server/
├── src/
│   └── index.ts
├── package.json
└── tsconfig.json
```

### Available Tools

| Tool | Description |
|------|-------------|
| `kas_search` | Search the knowledge base |
| `kas_ask` | Ask questions with AI-generated answers |
| `kas_capture` | Capture content to knowledge base |
| `kas_stats` | Get knowledge base statistics |
| `kas_review` | Get due review items |

### Configuration

Add to Claude Code settings (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "kas": {
      "command": "node",
      "args": ["/path/to/knowledge-activation-system/mcp-server/dist/index.js"],
      "env": {
        "KAS_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

### Build & Run

```bash
cd mcp-server
npm install
npm run build
```

---

## 2. iOS Shortcuts Integration

Simplified API endpoints designed for iOS Shortcuts app.

### Location
```
src/knowledge/api/routes/shortcuts.py
```

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/shortcuts/search` | GET | Search with text response |
| `/shortcuts/capture` | POST | Quick capture text |
| `/shortcuts/stats` | GET | Get statistics |
| `/shortcuts/review-count` | GET | Count due reviews |

### Example Shortcut: Search KAS

1. **Get Contents of URL**
   - URL: `http://your-server:8000/shortcuts/search?q=[query]`

2. **Get Dictionary Value** → `text`

3. **Show Result**

### Example Shortcut: Quick Capture

1. **Get Clipboard**

2. **Get Contents of URL** (POST)
   - URL: `http://your-server:8000/shortcuts/capture?text=[clipboard]&title=[title]`

3. **Show Notification** → "Captured to KAS"

---

## 3. Raycast Extension

Native Raycast extension for macOS.

### Location
```
integrations/raycast/
├── package.json
├── tsconfig.json
└── src/
    ├── search.tsx      # Search command
    ├── capture.tsx     # Quick capture
    ├── stats.tsx       # View statistics
    └── review.tsx      # Review due items
```

### Installation (Development)

```bash
cd integrations/raycast
npm install
npm run dev
```

### Installation (Production)

```bash
cd integrations/raycast
npm run build
# Import extension in Raycast
```

### Commands

| Command | Description | Shortcut |
|---------|-------------|----------|
| Search KAS | Search knowledge base | ⌘K |
| Quick Capture | Capture text/URL | ⌘⇧C |
| View Stats | Show statistics | - |
| Review Due | Show due items | - |

### Configuration

Set preferences in Raycast:
- **API URL**: `http://localhost:8000`

---

## 4. Browser Extension

Chrome/Firefox extension for web content capture.

### Location
```
integrations/browser-extension/
├── manifest.json
├── popup.html
├── popup.js
├── background.js
├── options.html
└── options.js
```

### Installation (Development)

**Chrome:**
1. Go to `chrome://extensions`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select `integrations/browser-extension/`

**Firefox:**
1. Go to `about:debugging`
2. Click "This Firefox"
3. Click "Load Temporary Add-on"
4. Select `manifest.json`

### Features

- **Popup Search**: Quick search from toolbar
- **Context Menu**: Right-click to save
  - Save selected text
  - Save link
  - Save page
- **Settings**: Configure API URL

### Configuration

Click extension icon → Settings:
- **API URL**: `http://localhost:8000`
- **Web URL**: `http://localhost:3000`

---

## 5. n8n Custom Node

Workflow automation node for n8n.

### Location
```
integrations/n8n/
├── package.json
├── credentials/
│   └── KasApi.credentials.ts
└── nodes/
    └── Kas/
        └── Kas.node.ts
```

### Installation

```bash
cd integrations/n8n
npm install
npm link

# In n8n directory
npm link n8n-nodes-kas
```

### Operations

| Operation | Description |
|-----------|-------------|
| Search | Search knowledge base |
| Capture | Capture content |
| Get Stats | Get statistics |
| Get Content | Get content by ID |

### Credentials

Create "KAS API" credentials in n8n:
- **Base URL**: `http://localhost:8000`
- **API Key**: (optional)

### Example Workflow

```
[Webhook] → [KAS: Search] → [IF: Has Results] → [Respond]
                                    ↓
                              [KAS: Capture]
```

---

## 6. Python SDK

Programmatic access to KAS from Python applications.

### Location
```
sdk/python/kas_client/
├── __init__.py
├── client.py
├── models.py
└── exceptions.py
```

### Installation

```bash
pip install -e sdk/python/
```

### Usage

```python
from kas_client import KASClient

async with KASClient("http://localhost:8000") as client:
    # Search
    results = await client.search("python patterns", limit=10)

    # Ask questions
    answer = await client.ask("How does RAG work?")

    # Capture content
    await client.capture(
        content="Important note...",
        title="My Note",
        tags=["note", "important"]
    )

    # Get statistics
    stats = await client.stats()

    # Spaced repetition
    items = await client.get_review_items()
    await client.submit_review(item.content_id, rating=3)
```

---

## 7. REST API

Direct HTTP access to all KAS features.

### Base URL
```
http://localhost:8000/api/v1/
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/search` | GET | Hybrid search |
| `/ask` | POST | AI-powered Q&A |
| `/content` | GET/POST | Content CRUD |
| `/content/{id}` | GET/PUT/DELETE | Single content |
| `/batch/search` | POST | Batch search |
| `/batch/delete` | POST | Batch delete |
| `/export` | GET | Export data |
| `/import` | POST | Import data |
| `/webhooks` | GET/POST | Webhook management |
| `/review/due` | GET | Due reviews |
| `/review/{id}` | POST | Submit review |

### Authentication

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/search?q=test
```

### Example: Search

```bash
curl "http://localhost:8000/api/v1/search?q=python+patterns&limit=10&rerank=true"
```

### Example: Capture

```bash
curl -X POST "http://localhost:8000/api/v1/capture" \
  -H "Content-Type: application/json" \
  -d '{"text": "Important note", "title": "My Note"}'
```

---

## 8. Web UI

Next.js-based web interface.

### Location
```
web/
├── src/
│   ├── app/           # Pages
│   ├── components/    # UI components
│   └── lib/           # Utilities
└── package.json
```

### Running

```bash
cd web
npm install
npm run dev
```

### Features

- Full-text search with filters
- Content management
- Knowledge graph visualization
- Spaced repetition reviews
- Analytics dashboard
- Settings management

### URL
```
http://localhost:3000
```

---

## Configuration Summary

| Integration | Config Location | Key Settings |
|-------------|-----------------|--------------|
| MCP Server | `~/.claude/settings.json` | KAS_API_URL |
| Raycast | Raycast Preferences | API URL |
| Browser Ext | Extension Options | apiUrl, webUrl |
| n8n | Credentials | baseUrl, apiKey |
| Python SDK | Constructor | base_url |
| Web UI | `.env.local` | NEXT_PUBLIC_API_URL |

---

## Troubleshooting

### Connection Refused
- Ensure API is running: `curl http://localhost:8000/health`
- Check Docker: `docker compose ps`

### Authentication Failed
- Verify API key in settings
- Check API key is valid: `curl -H "X-API-Key: KEY" http://localhost:8000/api/v1/search?q=test`

### Extension Not Loading
- Check browser developer console
- Verify manifest.json permissions
- Reload extension

### MCP Server Issues
- Rebuild: `cd mcp-server && npm run build`
- Check Claude Code logs
- Verify path in settings.json

---

## Publishing Checklist

### Raycast Store
- [ ] Add extension icons
- [ ] Complete package.json metadata
- [ ] Run `npm run publish`

### Chrome Web Store
- [ ] Add icons (16, 48, 128px)
- [ ] Create screenshots
- [ ] Write description
- [ ] Package as .zip
- [ ] Submit to Chrome Web Store

### n8n Community
- [ ] Add node icon
- [ ] Complete documentation
- [ ] Publish to npm
- [ ] Submit to n8n community nodes

---

**See individual integration directories for detailed documentation.**
