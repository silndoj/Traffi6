# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: PulseTraffic

Smart traffic signal optimization platform for Karlsruhe, built for the Cursor Hackathon (March 2026). Analyzes 589K real IoT sensor readings to prove that 86% of intersections need adaptive signal timing, and demonstrates Green Wave corridor optimization.

## Running

```bash
cd app/backend && python3 server.py
# Open http://localhost:8000

# Or with Docker:
cd app && docker compose up --build
```

If port 8000 is busy: `lsof -ti:8000 | xargs kill -9`

## Architecture

```
app/
├── backend/
│   ├── server.py          FastAPI + WebSocket (10fps streaming)
│   ├── simulation.py      Constant-pool simulation (750 vehicles on OSMnx roads)
│   ├── database.py        SQLite (304K readings, 50 sensors, 6,827 timestamps)
│   ├── analytics.py       Peak hours, anomaly detection, congestion grid
│   ├── signals.py         Signal analysis, green wave corridors (BFS chains)
│   ├── road_graph.pkl     Cached OSMnx graph (3,914 nodes, 5,700 edges)
│   └── sensor_positions.json  50 sensors mapped to road intersections
├── frontend/
│   ├── index.html         Narrative UI: Problem → Solution story
│   ├── js/app.js          WebSocket client, marker pool, Green Wave toggle
│   ├── css/style.css      Dark cinematic theme (Inter font, glassmorphism)
│   ├── mobile.html        Wallet-style mobile traffic card
│   └── assets/            Vehicle icons (car, truck, motor_bike, bicycle, foot)
├── data/traffic.db        SQLite database (imported from data.csv)
├── n8n/                   n8n workflow JSONs (data ingestion, anomaly alerter)
├── Dockerfile + docker-compose.yml
└── requirements.txt
```

## Key Systems

### Simulation (simulation.py)
- **750 constant vehicles** — never spawned/despawned, only redistributed
- **Attraction zones** — sensor data controls WHERE vehicles cluster
- **Traffic lights** — 749 intersections, vehicles stop at red, queue behind
- **Green Wave** — syncs light phases along 5 corridors (2-3km each, BFS chains)
- **Boundary containment** — vehicles teleport back if >4.5km from center
- **Anti-zigzag** — 3-node backtrack memory, dead-end avoidance, micro-edge skip

### Frontend (narrative UI)
- **No tabs** — single scrollable sidebar telling Problem → Solution story
- **Hero metric** — "Stopped at Red" counter with live percentage
- **Efficiency Score** — 0-100 composite metric with color-coded bar
- **Hero button** — "ENABLE GREEN WAVE" triggers corridors + light sync
- **Impact section** — slides in after toggle, shows before/after comparison
- **Heatmap** — 750 vehicle positions as heat points (Leaflet.heat)

### Data Flow
```
data.csv (210K rows) → SQLite DB (304K readings)
                              ↓
FastAPI startup → load timestamps → init simulation → pre-compute analytics
                              ↓
WebSocket /ws/traffic → stream {positions, stopped, anomalies, traffic_lights}
                              ↓
Frontend marker pool → update 750 markers at 10fps
```

## Dependencies
- Python: fastapi, uvicorn, osmnx, pandas, websockets
- Frontend: Leaflet 1.9.3, Leaflet.heat, Inter font (CDN)
- Data: SQLite, 43MB CSV

## Sensor Data Format (data.csv)
Two lane class formats in CSV:
- List: `[['car', 2], ['motorbike', 1]]`
- Dict: `[{'class': 'car', 'count': 2, 'subClass': None}]`

Vehicle types: car, motorbike, truck, single-unit-truck, articulated-truck, car-with-trailer, bicycle
