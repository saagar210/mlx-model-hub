# MLX Model Hub Frontend

Next.js 15 dashboard for managing MLX models, training jobs, and inference on Apple Silicon.

## Features

- **Dashboard**: Overview of models, training jobs, and system metrics
- **Models**: Browse, download, and manage MLX models from Hugging Face
- **Training**: Create and monitor LoRA fine-tuning jobs
- **Inference**: Interactive playground for testing models
- **Metrics**: System health and performance monitoring with Grafana integration

## Tech Stack

- **Framework**: Next.js 15 with App Router
- **UI Components**: shadcn/ui with Tailwind CSS v4
- **Data Fetching**: TanStack Query
- **Icons**: Lucide React
- **Notifications**: Sonner

## Getting Started

### Prerequisites

- Node.js 20+
- Backend API running at `http://localhost:8000`

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The app will be available at `http://localhost:3000`.

### Environment Variables

Create a `.env.local` file:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run start` | Start production server |
| `npm run lint` | Run ESLint |
| `npm run test:e2e` | Run Playwright E2E tests |
| `npm run test:e2e:ui` | Run E2E tests with UI |

## Project Structure

```
frontend/
├── src/
│   ├── app/                    # Next.js App Router pages
│   │   ├── page.tsx           # Dashboard
│   │   ├── models/            # Models pages
│   │   ├── training/          # Training pages
│   │   ├── inference/         # Inference playground
│   │   └── metrics/           # Metrics dashboard
│   ├── components/
│   │   ├── layout/            # Layout components
│   │   └── ui/                # shadcn/ui components
│   └── lib/
│       ├── api.ts             # API client
│       ├── hooks/             # TanStack Query hooks
│       └── utils.ts           # Utility functions
├── e2e/                       # Playwright E2E tests
└── playwright.config.ts       # Playwright configuration
```

## Pages

### Dashboard (`/`)
- System overview with key metrics
- Quick actions for common tasks
- Real-time system status

### Models (`/models`)
- List all available and cached models
- Download models from Hugging Face
- Load/unload models for inference
- Delete cached models

### Model Detail (`/models/[id]`)
- Detailed model information
- Quick actions (inference, fine-tune)
- External links to Hugging Face

### Training (`/training`)
- List all training jobs
- Create new LoRA fine-tuning jobs
- Monitor job progress and metrics
- Cancel running jobs

### Inference (`/inference`)
- Interactive chat playground
- Model selection from cached models
- Configurable parameters (temperature, top_p, max_tokens)
- Performance metrics (TTFT, tokens/second)

### Metrics (`/metrics`)
- API health status
- System metrics (models loaded, active inferences)
- Storage usage
- Links to Prometheus, Grafana, MLflow

## API Integration

The frontend communicates with the backend API using TanStack Query for:
- Automatic caching and refetching
- Optimistic updates
- Error handling with toast notifications
- Polling for live metrics and job status

## Testing

E2E tests are written using Playwright:

```bash
# Run all tests
npm run test:e2e

# Run tests with UI
npm run test:e2e:ui

# Run specific test file
npx playwright test e2e/navigation.spec.ts
```

## Development

### Adding a new page

1. Create a new directory in `src/app/`
2. Add a `page.tsx` file with the page component
3. Wrap with `DashboardLayout` for consistent navigation
4. Add navigation link in `src/components/layout/sidebar.tsx`

### Adding API hooks

1. Add types to `src/lib/api.ts`
2. Add API functions to `src/lib/api.ts`
3. Create hook in `src/lib/hooks/`
4. Export from `src/lib/hooks/index.ts`
