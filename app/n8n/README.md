# n8n Workflows — Traffic Data Platform

Two automated workflows for ingesting traffic sensor data and detecting anomalies.

## Prerequisites

- n8n running at `http://localhost:5678`
- FastAPI backend running at `http://localhost:8000`
- SmartCity API key

## Environment Variables

Set these in n8n (Settings > Environment Variables):

| Variable | Description |
|----------|-------------|
| `SMARTCITY_API_KEY` | API key for SmartCity Heilbronn traffic sensor API |

## Workflows

### 1. Traffic Data Ingestion (`data_ingestion.json`)

Polls the SmartCity API every 2 minutes and pushes sensor readings to the backend.

**Flow:** Schedule (2min) → Fetch SmartCity API → Check success → Transform response → POST to `/api/ingest`

On API failure, errors are logged with timestamp and status code.

### 2. Anomaly Alerter (`anomaly_alerter.json`)

Checks traffic stats every 10 minutes for anomalies (volume spikes >2 standard deviations above mean, missing data).

**Flow:** Schedule (10min) → Fetch `/api/stats` → Detect anomalies → IF anomaly → Format alert → POST webhook

Update the webhook URL in the "Send Alert Webhook" node to point to your notification endpoint (Slack, Discord, email service, etc.).

## Importing into n8n

### Option A: Via n8n UI

1. Open n8n at `http://localhost:5678`
2. Click the **+** button or go to **Workflows** > **Import from File**
3. Select `data_ingestion.json`, then repeat for `anomaly_alerter.json`
4. Set the `SMARTCITY_API_KEY` environment variable in Settings
5. Activate each workflow via the toggle in the top-right

### Option B: Via API (requires API key)

```bash
# Set your n8n API key
export N8N_API_KEY="your-api-key"

# Import workflows
curl -X POST http://localhost:5678/api/v1/workflows \
  -H "Content-Type: application/json" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -d @workflows/data_ingestion.json

curl -X POST http://localhost:5678/api/v1/workflows \
  -H "Content-Type: application/json" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -d @workflows/anomaly_alerter.json
```

## Backend API Endpoints Required

These endpoints must exist on the FastAPI backend (`http://localhost:8000`):

- **`POST /api/ingest`** — Accepts `{ "readings": [{ "sensor_id", "timestamp", "vehicle_type", "count" }] }`
- **`GET /api/stats`** — Returns `{ "total_vehicles": int, "by_type": { "car": int, ... } }`
