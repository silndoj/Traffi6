# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**KI Kommune 2024** — a real-time traffic simulation and visualization platform for Karlsruhe, Germany, built during the KI Kommune 2024 hackathon. It simulates pedestrians, cars, bikes, trucks, and motorbikes moving along real road networks from OpenStreetMap, displayed on an interactive Leaflet.js map.

## Running the Application

```bash
# Start the web server (serves map + simulation at http://localhost:8000)
cd KI_Kommune_2024/server && python3 server.py

# Run the Streamlit analytics dashboard
cd KI_Kommune_2024/scripts && streamlit run web.py

# Run standalone traffic analysis scripts
cd KI_Kommune_2024/scripts && python3 main.py
cd KI_Kommune_2024/scripts && python3 playground.py
```

Or use the Makefile from `KI_Kommune_2024/`:
```bash
make   # runs cd server && python3 server.py
```

## Python Dependencies

- `osmnx` — downloads real road network graphs from OpenStreetMap
- `folium` — generates the base map HTML
- `matplotlib` — traffic data plotting and diagrams
- `pandas`, `numpy` — data analysis
- `streamlit` — interactive dashboard (scripts/web.py)
- `requests` — external API calls to SmartCity Heilbronn traffic sensor API

## Architecture

### Simulation Engine (`server/`)

The core is a graph-based traffic simulation:

- **`graph.py`** — The simulation engine. `Graph` class pulls real road intersections via OSMnx, creates `Node` objects (which act as sensors), and spawns `Participant` objects that traverse edges. `get_large_graph()` creates the default simulation: 400 cars, 20 trucks, 40 pedestrians, 40 bicycles, 40 motorbikes in a 3km radius around central Karlsruhe (49.00587, 8.40162).
- **`server.py`** — Python `http.server`-based web server on port 8000. On startup, generates `map.html` via Folium with sensor markers. The `/data` endpoint advances the simulation by one tick (`graph.pass_time()`) and returns all participant positions as JSON.
- **`index.html`** — Frontend. Embeds the Folium map in an iframe, polls `/data` every 1 second, clears old Leaflet markers, and places new ones with vehicle-type icons (car.png, foot.png, bicycle.png, truck.png, motor_bike.png).
- **`diagram.py`** — Filters sensors by geographic radius and plots detection counts over time.
- **`api_request.py`** — Client for the SmartCity Heilbronn traffic sensor API (`APIs.smartcity.hn`). Requires `API_KEY` env var.

### Key Simulation Concepts

- **Node** = road intersection + optional sensor. Sensors detect participants within a configurable meter radius. Nodes have weighted attraction toward city center.
- **Participant** = a traffic entity (car/foot/bicycle/truck/motor_bike) that moves between nodes at a configured speed (meters/sec). When reaching a target node, picks next node randomly weighted by proximity to center.
- **`pass_time()`** = advances all participants by one simulation second × speed multiplier.

### Data Analysis (`scripts/`)

- **`sensor_data.py`** — Generates simulated 24-hour traffic data with random counts.
- **`main.py`**, **`playground.py`**, **`alo.py`** — Various analysis scripts: peak detection, anomaly detection (>2σ), morning/afternoon rush hour analysis, matplotlib visualizations.
- **`web.py`** — Streamlit dashboard combining all analyses with interactive charts.

### Data Parser (`parser/`)

- **`parser.py`** — Parses the JSON sensor data file (`data2/Daten_20241105.json`, 70MB) into typed dataclasses (`SensorRecord`, `Lane`, `Vehicle`). Includes filtering functions (e.g., `get_not_motorized` filters for non-car/truck/motorbike records).

## Data Files

- **`data.csv`** (43MB, 210K rows) — Flattened sensor records with columns: `_id`, `timezone`, `timestamp`, `sensor_id`, `weather_bitmap`, `mq_timestamp`, `lane1.total`, `lane1.classes`, `lane2.total`, `lane2.classes`
- **`KI_Kommune_2024/data2/Daten_20241105.json`** (70MB) — Raw JSON sensor data from 2024-11-05. Each record has two lanes with vehicle class counts (car, motorbike, truck, etc.)

## Important Notes

- The simulation coordinate system uses lat/lon (X=latitude, Y=longitude) centered on Karlsruhe.
- Distance conversions use approximations: `dx * 73 * 1600` for longitude-to-meters, `dy * 111.32 * 1600` for latitude-to-meters.
- The server is stateful — the `Graph` object is created once at module load and mutated on each `/data` request.
- `scripts/` modules import from each other using relative imports — run them from within the `scripts/` directory.
- Comments and variable names are a mix of German and English.
