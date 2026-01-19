# KAS Monitoring Stack

Prometheus + Grafana monitoring for Knowledge Activation System.

## Quick Start

```bash
cd monitoring
docker compose up -d
```

## Access

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3001
  - Username: `admin`
  - Password: `kasadmin`

## Metrics Available

The KAS API exposes Prometheus metrics at `/metrics`:

- `kas_http_requests_total` - Total HTTP requests by endpoint, method, status
- `kas_http_request_duration_seconds` - Request latency histogram
- `kas_documents_total` - Total documents in the system
- `kas_chunks_total` - Total chunks in the system
- `kas_search_queries_total` - Total search queries
- `kas_review_items_total` - Total items in review queue

## Grafana Dashboards

Pre-configured dashboard:
- **KAS Overview** - Main dashboard with request rates, latency, and document counts

## Architecture

```
┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│   KAS API      │────▶│   Prometheus   │────▶│    Grafana     │
│  :8000/metrics │     │     :9090      │     │     :3001      │
└────────────────┘     └────────────────┘     └────────────────┘
```
