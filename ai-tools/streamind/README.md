# StreamMind

Real-time screen analysis with AI. An assistant that can "see" your screen and understand what you're doing.

## What It Does

```
Your Screen → AI Vision → Instant Understanding

"What's that error?"

"That's a TypeError in UserList.jsx line 45.
You're calling .map() on 'users' but it's undefined..."
```

## Why This Exists

- **Multimodal AI is THE 2025 trend**
- No one's doing real-time screen analysis locally
- Uses llama3.2-vision:11b (already installed)
- 100% local, 100% private

## Quick Start

```bash
# Install dependencies
pip install -e .

# Run StreamMind
streamind serve

# Ask about your screen
streamind ask "What's that error?"
```

## Status

- [ ] Screen capture engine
- [ ] Vision analysis (Ollama)
- [ ] Context manager
- [ ] CLI interface
- [ ] Menu bar app

## Documentation

- [STRATEGY.md](./STRATEGY.md) - Full implementation plan
- [CLAUDE.md](./CLAUDE.md) - Context for Claude Code

## Privacy

- All processing happens locally on your Mac
- No data sent to any server
- App blocklist for sensitive apps
- Auto-delete history option

## License

MIT
