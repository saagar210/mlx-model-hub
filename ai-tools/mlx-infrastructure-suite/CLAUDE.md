# MLX Infrastructure Suite

## Project Overview
A suite of 3 interconnected tools that establish you as THE MLX infrastructure expert on Apple Silicon. Each tool builds on the previous, creating a cohesive ecosystem.

## The Suite
1. **MLXDash** - Menu bar monitor for ML workloads (Week 1)
2. **MLXCache** - Shared model weight cache (Weeks 2-3)
3. **SwiftMLX** - Xcode templates for MLX apps (Weeks 4-6)

## Why This Stack
- Zero competition in Mac-specific ML infrastructure
- Ships incrementally (momentum from day 1)
- Each piece enhances the others
- Monetizable with premium features
- Perfect Apple Silicon focus

## Tech Stack
- **MLXDash**: Swift + SwiftUI (native menu bar app)
- **MLXCache**: Python + SQLite + CLI
- **SwiftMLX**: Swift Package + Xcode templates

## Prerequisites (Already Installed)
- MLX 0.30+, mlx-lm, mlx-tuning-fork
- Ollama with models (deepseek-r1, qwen2.5-coder, llama3.2-vision)
- mlx-omni-server for OpenAI-compatible endpoints
- Existing MLX projects: MLX Model Hub, Unified MLX App, Silicon Studio

## Success Metrics
- MLXDash: 1K+ downloads in first month
- MLXCache: 50%+ disk savings for average user
- SwiftMLX: Featured in Apple dev community

## Commands
```bash
# Development
cd /Users/d/claude-code/ai-tools/mlx-infrastructure-suite

# Run tests (when implemented)
swift test  # For Swift projects
pytest      # For Python components
```

## Related Projects
- `/Users/d/claude-code/ai-tools/mlx-model-hub/` - Model management
- `/Users/d/claude-code/ai-tools/unified-mlx-app/` - Inference UI
- `/Users/d/claude-code/ai-tools/silicon-studio-audit/` - Fine-tuning UI
