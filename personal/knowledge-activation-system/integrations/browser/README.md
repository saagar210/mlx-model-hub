# Knowledge Engine Browser Extension

A Chrome/Firefox extension for clipping web content to your Knowledge Engine.

## Features

- **One-Click Page Clipping**: Save entire pages with extracted content
- **Selection Clipping**: Clip selected text with context
- **URL Clipping**: Fetch and ingest any URL
- **Context Menu Integration**: Right-click to clip
- **Keyboard Shortcuts**: Alt+Shift+K (page), Alt+Shift+S (selection)
- **Selection Toolbar**: Quick actions when selecting text

## Installation

### Chrome/Edge (Development)

1. Navigate to `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select the `integrations/browser` directory

### Firefox (Development)

1. Navigate to `about:debugging#/runtime/this-firefox`
2. Click "Load Temporary Add-on..."
3. Select `manifest.json` from the `integrations/browser` directory

## Configuration

1. Click the extension icon
2. Click "Settings" in the footer
3. Configure:
   - **API URL**: Your Knowledge Engine server (default: `http://localhost:8000`)
   - **API Key**: Optional authentication key
   - **Namespace**: Organization namespace (default: `browser`)

## Usage

### Clip Page
- Click the extension icon and click "Clip Page"
- Or use keyboard shortcut `Alt+Shift+K`
- Or right-click on page and select "Clip entire page to Knowledge Engine"

### Clip Selection
- Select text on any page
- Click "Clip" on the popup toolbar
- Or use keyboard shortcut `Alt+Shift+S`
- Or right-click and select "Clip selection to Knowledge Engine"

### Clip URL
- Click the extension icon
- Enter a URL in the input field
- Click the + button

## Building for Production

```bash
# Install dependencies (none required for vanilla JS)
# Create production build
zip -r knowledge-engine-extension.zip . \
  -x "*.git*" \
  -x "README.md" \
  -x "*.DS_Store"
```

## File Structure

```
browser/
├── manifest.json          # Extension manifest
├── popup.html             # Popup UI
├── options.html           # Settings page
├── src/
│   ├── background.js      # Service worker
│   ├── content.js         # Content script
│   ├── popup.js           # Popup logic
│   └── options.js         # Settings logic
├── styles/
│   ├── popup.css          # Popup styles
│   ├── content.css        # Content script styles
│   └── options.css        # Settings styles
└── icons/
    ├── icon16.png
    ├── icon32.png
    ├── icon48.png
    └── icon128.png
```

## Permissions

- `activeTab`: Access current tab content for clipping
- `storage`: Save extension settings
- `contextMenus`: Add right-click menu items
- `host_permissions`: Connect to Knowledge Engine API

## Development

The extension uses vanilla JavaScript with no build step required. Simply edit files and reload the extension.

### Testing

1. Load the extension in development mode
2. Open any webpage
3. Test clipping functionality
4. Check the console for any errors

### Icons

Generate icons from an SVG:
```bash
# Using ImageMagick
for size in 16 32 48 128; do
  convert -background transparent icon.svg -resize ${size}x${size} icon${size}.png
done
```
