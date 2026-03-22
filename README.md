# PulseTraffic — Smart Traffic Signal Optimization

Real-time traffic simulation and signal optimization platform for Karlsruhe, Germany. Analyzes 304,018 real IoT sensor readings to prove that 86% of intersections need adaptive timing, then demonstrates Green Wave corridor optimization that reduces stopped vehicles by 17%.

**[Live Demo](https://8ef220895df8f085-153-92-90-3.serveousercontent.com)** · **[Pitch Deck](https://8ef220895df8f085-153-92-90-3.serveousercontent.com/pitch.html)**

---

## The Problem

Fixed traffic signals waste time. Our analysis of 304,018 real sensor readings from 50 IoT traffic sensors across 6 days proves:

- **86%** of intersections have traffic too unpredictable for fixed timing
- **Peak hour (17:00)** sees 2x more traffic than off-peak
- **23%** of vehicles stuck at red lights at any given moment

## The Solution: Green Wave

Synchronize traffic lights along optimized corridors so drivers hit consecutive green lights without stopping.

- **5 corridors** identified via Dijkstra shortest-path on real road network
- **2-3 km each**, connecting high-traffic sensor pairs
- **Hero car** demonstrates the concept: drives Spassbecken → Heidesee (6.6km) hitting every green
- **17% fewer vehicles stopped** when Green Wave is enabled
- **977 vehicle-hours saved daily** across the city

## How It Works

```
Real Sensor Data (304K readings, 50 sensors, 6 days)
        ↓
SQLite Database → FastAPI Backend
        ↓
OSMnx Road Network (3,914 nodes, 5,700 edges)
        ↓
Constant-Pool Simulation (750 vehicles, always on roads)
        ↓
WebSocket 10fps → Leaflet.js Dark Dashboard
        ↓
One-Click Green Wave → Before/After Impact
```

### Key Features

- **750 vehicles** driving on real Karlsruhe roads (OSMnx)
- **749 traffic lights** cycling green/yellow/red — vehicles obey them
- **Vehicle queuing** at red lights with anti-overlap
- **Green Wave** synchronizes corridor signals + redirects 30% of traffic
- **Hero car** with glowing marker drives the optimized route
- **Heatmap** overlay showing traffic density
- **Anomaly detection** (1.5σ threshold) at rush hour
- **Efficiency Score** (0-100) composite metric
- **Mobile card** for citizens via QR code
- **n8n workflows** for automated data ingestion and anomaly alerting

## Quick Start

```bash
# Clone
git clone https://github.com/silndoj/Traffi6.git
cd Traffi6

# Install dependencies
pip install fastapi uvicorn pandas osmnx

# Run
cd app/backend && python3 server.py

# Open http://localhost:8000
```

### Docker

```bash
cd app && docker compose up --build
# Open http://localhost:8000
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, WebSocket, SQLite |
| Simulation | OSMnx (real road graph), constant-pool model |
| Frontend | Leaflet.js, Leaflet.heat, vanilla JS |
| Routing | Dijkstra shortest-path for corridors |
| Data | 304,018 real IoT sensor readings (CSV → SQLite) |
| Automation | n8n workflows (data ingestion + anomaly alerts) |
| Deployment | Docker, Serveo tunnel |
| Design | Inter font, dark cinematic theme, narrative UI |

## Data

Real traffic sensor data from SmartCity IoT platform:
- **50 sensors** across Karlsruhe
- **6 days** (Oct 31 – Nov 5, 2024)
- **6,827 timestamps**
- Vehicle types: car (65%), motorbike (20%), truck (14%), bicycle (0.3%)
- Two lane formats handled (list + dict serialization)

## Project Structure

```
app/
├── backend/
│   ├── server.py          # FastAPI + WebSocket streaming
│   ├── simulation.py      # 750-vehicle constant pool on OSMnx roads
│   ├── database.py        # SQLite data access
│   ├── analytics.py       # Peak hours, anomaly detection
│   ├── signals.py         # Green wave corridor algorithm (Dijkstra chains)
│   └── road_graph.pkl     # Cached road network
├── frontend/
│   ├── index.html         # Narrative UI: Problem → Solution
│   ├── js/app.js          # WebSocket client, marker pool, Green Wave toggle
│   ├── css/style.css      # Cinematic dark theme
│   ├── mobile.html        # Mobile traffic card
│   └── pitch.html         # Pitch deck page
├── n8n/workflows/         # Data ingestion + anomaly alerter
├── Dockerfile + docker-compose.yml
└── data/traffic.db        # SQLite database
```

## Sponsors Used

- **Cursor** — AI-powered development environment
- **n8n** — Automated data pipeline workflows

## Team

Built at the Cursor Hackathon, March 2026.

## License

MIT
