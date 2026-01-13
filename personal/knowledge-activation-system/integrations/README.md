# Knowledge Engine Integrations

This directory contains integrations for various platforms and tools.

## Available Integrations

### Browser Extension
Chrome/Firefox extension for web clipping and content capture.

**Features:**
- One-click page clipping
- Text selection capture
- URL clipping
- Context menu integration
- Keyboard shortcuts

**Location:** `browser/`

### Obsidian Plugin
Obsidian plugin for vault synchronization and search.

**Features:**
- Semantic search across vault
- Auto-sync on save
- Bulk sync all notes
- Exclude folder configuration
- Search result linking

**Location:** `obsidian/`

### VS Code Extension
VS Code extension for code documentation and search.

**Features:**
- Knowledge base search
- AI-powered Q&A
- Selection ingestion
- File ingestion
- Status bar indicator

**Location:** `vscode/`

## Installation

### Browser Extension (Chrome)
1. Navigate to `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select `integrations/browser`

### Obsidian Plugin
1. Copy `obsidian/` to `.obsidian/plugins/knowledge-engine/`
2. Run `npm install && npm run build`
3. Enable plugin in Obsidian settings

### VS Code Extension
1. Copy `vscode/` to your extensions directory
2. Run `npm install && npm run compile`
3. Restart VS Code

## Configuration

All integrations share common configuration options:

| Option | Description | Default |
|--------|-------------|---------|
| `apiUrl` | Knowledge Engine API URL | `http://localhost:8000` |
| `apiKey` | Optional authentication key | `` |
| `namespace` | Content namespace | Integration-specific |

## Development

Each integration has its own build process:

```bash
# Browser extension (no build required)
cd browser

# Obsidian plugin
cd obsidian
npm install
npm run dev  # Watch mode
npm run build  # Production

# VS Code extension
cd vscode
npm install
npm run watch  # Watch mode
npm run compile  # Production
```

## Architecture

```
integrations/
├── browser/           # Chrome/Firefox extension
│   ├── manifest.json
│   ├── popup.html
│   ├── options.html
│   ├── src/
│   └── styles/
├── obsidian/          # Obsidian plugin
│   ├── manifest.json
│   ├── package.json
│   ├── src/
│   └── styles.css
└── vscode/            # VS Code extension
    ├── package.json
    ├── tsconfig.json
    └── src/
```

## API Endpoints Used

All integrations interact with the Knowledge Engine API:

- `GET /health` - Connection health check
- `POST /v1/search` - Semantic search
- `POST /v1/query` - RAG Q&A
- `POST /v1/ingest/text` - Text ingestion
- `POST /v1/ingest/url` - URL ingestion
