# MLX Infrastructure Suite

The "plumbing" that every MLX developer needs. Three tools that make local ML on Mac seamless.

## The Suite

| Tool | Description | Build Time |
|------|-------------|------------|
| **MLXDash** | Menu bar monitor for ML workloads | 1 week |
| **MLXCache** | Shared model weight cache | 2 weeks |
| **SwiftMLX** | Xcode templates for MLX apps | 3 weeks |

## Why This Exists

- **No competition** in Mac-specific ML infrastructure
- Ships incrementally (momentum from day 1)
- Each piece enhances the others
- Perfect Apple Silicon focus

## Quick Start

```bash
# Start with MLXDash (menu bar monitor)
cd mlxdash
swift build
open .build/debug/MLXDash.app
```

## Status

- [ ] MLXDash - Not started
- [ ] MLXCache - Not started
- [ ] SwiftMLX - Not started

## Documentation

- [STRATEGY.md](./STRATEGY.md) - Full implementation plan
- [CLAUDE.md](./CLAUDE.md) - Context for Claude Code

## License

MIT
