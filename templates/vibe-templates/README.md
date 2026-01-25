# Vibe Templates

Smart project generator for vibe coding.

## Installation

```bash
uv tool install -e .
```

## Usage

```bash
# List available templates
vibe list

# Create a new project (interactive)
vibe new

# Create a new project (quick mode)
vibe new python-api my-backend
vibe new python-ml my-ai-app
vibe new nextjs my-frontend
vibe new fullstack my-app

# With optional features
vibe new python-api my-backend --docker --tests --ci
```

## Templates

| Template | Description | Destination |
|----------|-------------|-------------|
| `python-api` | FastAPI + uvicorn + pydantic | `personal/` |
| `python-ml` | MLX + Gradio | `ai-tools/` |
| `nextjs` | Next.js 14 + TypeScript + Tailwind | `personal/` |
| `fullstack` | Python API + Next.js frontend | `personal/` |
