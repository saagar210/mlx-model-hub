# Usage Instructions

This is a cloudflare workers + html/css/js + hono template.
This template serves static files from `public/` and exposes optional API routes under `/api/*` via the Worker.

- Dev: `bun run dev` (wrangler dev)
- Build: `bun run build` (wrangler build)
- Deploy: `bun run deploy` (wrangler deploy)
- Lint: `bun run lint` (prints a helpful message; add ESLint/Biome if needed)

Project structure:
- `public/` — `index.html`, `styles.css`, `app.js`
- `worker/index.ts` — minimal fetch handler; handles `/api/health` and returns 404 for other `/api/*`
- `wrangler.jsonc` — serves `public` as static assets; routes `/api/*` to the Worker first

Tips:
- If you need a small API, add routes in `worker/index.ts` under `/api/*`.
- For single‑page routing, 404s fall back to `index.html` (SPA mode).

