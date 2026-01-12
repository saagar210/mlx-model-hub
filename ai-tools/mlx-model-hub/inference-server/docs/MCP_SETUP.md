# MCP (Model Context Protocol) Setup Guide

This guide explains how to connect your Unified MLX App to Claude Desktop and Claude Code.

## What is MCP?

MCP (Model Context Protocol) allows AI assistants like Claude to use external tools. With MCP enabled, Claude can:
- Generate text using your local Qwen model
- Analyze images using your local vision model
- Convert text to speech using Kokoro
- Transcribe audio using Whisper

All processing happens **locally on your Mac** - no data leaves your machine.

## Setup Options

### Option 1: HTTP API (Recommended for Claude Code)

The Unified MLX App exposes MCP endpoints at `http://localhost:8080/mcp`.

**Available Endpoints:**
- `GET /mcp/tools` - List available tools
- `POST /mcp/call` - Call a tool
- `GET /mcp/info` - Server information

**Example Tool Call:**
```bash
curl -X POST http://localhost:8080/mcp/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_text",
    "arguments": {
      "prompt": "Explain quantum computing in simple terms",
      "max_tokens": 500
    }
  }'
```

### Option 2: Stdio Server (For Claude Desktop)

For Claude Desktop integration, use the standalone MCP server script.

**Step 1: Find your Python path**
```bash
which python
# Or if using mise:
~/.local/share/mise/installs/python/3.12.12/bin/python
```

**Step 2: Create Claude Desktop config**

Create or edit `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "unified-mlx": {
      "command": "/Users/d/.local/share/mise/installs/python/3.12.12/bin/python",
      "args": ["/Users/d/claude-code/ai-tools/unified-mlx-app/mcp_server.py"],
      "env": {
        "PYTHONPATH": "/Users/d/claude-code/ai-tools/unified-mlx-app/src"
      }
    }
  }
}
```

**Step 3: Restart Claude Desktop**

After saving the config, restart Claude Desktop. You should see "unified-mlx" in the MCP servers list.

## Available Tools

### generate_text
Generate text using the local Qwen language model.

```json
{
  "name": "generate_text",
  "arguments": {
    "prompt": "Write a haiku about coding",
    "system_prompt": "You are a creative poet.",
    "max_tokens": 100,
    "temperature": 0.8
  }
}
```

### analyze_image
Analyze images using the local vision model.

```json
{
  "name": "analyze_image",
  "arguments": {
    "image_path": "/path/to/image.png",
    "prompt": "What's in this image?",
    "max_tokens": 512
  }
}
```

### speak_text
Convert text to speech using Kokoro TTS.

```json
{
  "name": "speak_text",
  "arguments": {
    "text": "Hello, this is a test of local text to speech.",
    "voice": "a",
    "speed": 1.0
  }
}
```
Returns the path to the generated audio file.

### transcribe_audio
Transcribe audio files using local Whisper.

```json
{
  "name": "transcribe_audio",
  "arguments": {
    "audio_path": "/path/to/audio.wav"
  }
}
```

### get_model_status
Get status of loaded models and memory usage.

```json
{
  "name": "get_model_status",
  "arguments": {}
}
```

## Troubleshooting

### Check MCP server logs
```bash
tail -f /tmp/unified-mlx-mcp.log
```

### Test the HTTP endpoint
```bash
curl http://localhost:8080/mcp/info
```

### Verify Python environment
```bash
~/.local/share/mise/installs/python/3.12.12/bin/python -c "from unified_mlx_app.mcp import MCPServer; print('OK')"
```

### Common Issues

1. **"Module not found"**: Ensure PYTHONPATH includes the `src` directory
2. **"Connection refused"**: Make sure the Unified MLX App is running
3. **"Model loading slow"**: First call loads models into memory (takes 5-30 seconds)

## Integration with Other Apps

The HTTP MCP endpoint can be used by any application that supports HTTP:

- **AnythingLLM**: Configure as custom endpoint
- **Open WebUI**: Add as tool provider
- **Custom scripts**: Use curl or any HTTP client

## Security Notes

- The MCP server only binds to localhost (127.0.0.1)
- No authentication is required (local-only access)
- All model inference happens on-device
- No data is sent to external servers
