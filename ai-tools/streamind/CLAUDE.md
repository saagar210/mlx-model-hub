# StreamMind - Multimodal Intelligence Platform

## Project Overview
Real-time screen + AI reasoning. An AI that can "see" your screen and understand what you're doing. Like pair programming with someone who has eyes.

## Why This Project
- Multimodal AI is THE hottest trend in 2025
- No one's doing real-time screen analysis locally
- Uses your existing vision models (llama3.2-vision:11b)
- Incredibly useful demo potential
- Can expand into a full platform

## Core Concept
```
Your Screen → Continuous Capture → Vision Model Analysis → Contextual AI
     ↓                                                         ↓
"What's that error?"                               "That's a null pointer
                                                   exception in line 45..."
```

## Tech Stack
- **Screen Capture**: macOS ScreenCaptureKit (Swift) or Python mss
- **Vision Model**: llama3.2-vision:11b via Ollama
- **Reasoning**: deepseek-r1:14b for complex analysis
- **UI**: Menu bar app (Swift) or Electron
- **Storage**: SQLite for session history

## Prerequisites (Already Installed)
- Ollama with llama3.2-vision:11b (just installed!)
- deepseek-r1:14b for reasoning
- Unified MLX App (has vision infrastructure)
- Knowledge Activation System (for indexing screenshots)

## Success Metrics
- Response time <3 seconds for screen analysis
- "What's that error?" works 90% of the time
- Viral demo potential (record and share)

## Commands
```bash
# Development
cd /Users/d/claude-code/ai-tools/streamind

# Run StreamMind
python -m streamind serve

# Run with UI
streamind --ui

# Run tests
pytest
```

## Related Projects
- `/Users/d/claude-code/ai-tools/unified-mlx-app/` - Vision infrastructure
- `/Users/d/claude-code/personal/knowledge-activation-system/` - Could index screenshots
