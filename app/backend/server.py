"""FastAPI server streaming traffic simulation data over WebSocket."""

import asyncio
import json
import math
import os
import random
import sys

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import database
from analytics import (
    compute_peak_hours,
    compute_sensor_stats,
    detect_anomalies,
    compute_congestion_grid,
    compute_traffic_status,
)
from signals import (
    compute_intersection_analysis,
    find_coordination_pairs,
    compute_city_summary,
    model_signal_recommendations,
    model_green_wave_corridors,
)

# ---------------------------------------------------------------------------
# Sensor mapping — reuse the GIS module from the old codebase
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'KI_Kommune_2024', 'server'))
from sensor_mapping import load_or_create_mapping

# ---------------------------------------------------------------------------
# Vehicle type normalisation (CSV classes → frontend icon names)
# ---------------------------------------------------------------------------
VEHICLE_TYPE_MAP = {
    "car": "car",
    "Car": "car",
    "truck": "truck",
    "Truck": "truck",
    "bicycle": "bicycle",
    "Bicycle": "bicycle",
    "motorbike": "motor_bike",
    "Motorbike": "motor_bike",
    "motor_bike": "motor_bike",
    "pedestrian": "foot",
    "Pedestrian": "foot",
    "foot": "foot",
    "bus": "truck",
    "Bus": "truck",
}

# ---------------------------------------------------------------------------
# Fallback simulation (scatter-based) when real engine is unavailable
# ---------------------------------------------------------------------------


class FallbackSimulation:
    """Scatter-based fallback until real simulation is ready."""

    def __init__(self, sensor_positions):
        self.sensor_positions = sensor_positions
        self._readings = {}

    def update_from_data(self, readings):
        self._readings = readings

    def tick(self, dt):
        pass

    def get_positions(self):
        markers = []
        for sensor_id, vehicles in self._readings.items():
            if sensor_id not in self.sensor_positions:
                continue
            lat, lon = self.sensor_positions[sensor_id]
            for vtype, count in vehicles:
                mapped = VEHICLE_TYPE_MAP.get(vtype, vtype)
                for _ in range(count):
                    angle = random.uniform(0, 2 * math.pi)
                    r = math.sqrt(random.random()) * 0.0008
                    markers.append({
                        "X": lat + r * math.cos(angle),
                        "Y": lon + r * math.sin(angle),
                        "TYPE": mapped,
                        "ID": 0,
                    })
        return markers


# ---------------------------------------------------------------------------
# Application bootstrap
# ---------------------------------------------------------------------------

database.init_db()

sensor_volumes = database.get_sensor_volumes()
sensor_ids = list(sensor_volumes.keys())

MAP_HTML = os.path.join(
    os.path.dirname(__file__), '..', '..', 'KI_Kommune_2024', 'server', 'map.html',
)
POSITIONS_JSON = os.path.join(os.path.dirname(__file__), 'sensor_positions.json')

sensor_positions = load_or_create_mapping(
    sensor_ids,
    sensor_volumes,
    map_html_path=MAP_HTML,
    output_path=POSITIONS_JSON,
)

try:
    from simulation import TrafficSimulation
    sim = TrafficSimulation(sensor_positions)
    print("[server] Using real TrafficSimulation engine")
except Exception:
    sim = FallbackSimulation(sensor_positions)
    print("[server] simulation.py not available — using FallbackSimulation")

timestamps = database.get_timestamps()

# Find first daytime timestamp with traffic (skip night — demo should show busy city)
_start_index = 0
for _i, _ts in enumerate(timestamps):
    hour_str = _ts[11:13] if len(_ts) > 13 else ""
    hour = int(hour_str) if hour_str.isdigit() else -1
    if hour < 7 or hour > 20:
        continue
    _readings = database.get_readings_at(_ts)
    _total = sum(sum(c for _, c in v) for v in _readings.values())
    if _total >= 50:
        _start_index = _i
        sim.update_from_data(_readings)
        for _ in range(10):
            sim.tick(0.5)
        print(f"[server] Starting at index {_i} ({_ts}) with {_total} vehicles")
        break

# Pre-compute analytics on startup
sensor_stats = compute_sensor_stats()
peak_hours = compute_peak_hours()
print(f"[server] Peak hours computed, sensor stats ready")

# Signal intelligence
import json as _json
with open(os.path.join(os.path.dirname(__file__), 'sensor_positions.json')) as _f:
    _sensor_positions_raw = {k: tuple(v) for k, v in _json.load(_f).items()}

signal_analysis = compute_intersection_analysis()
coordination_pairs = find_coordination_pairs(_sensor_positions_raw)
city_summary = compute_city_summary(signal_analysis, coordination_pairs)
signal_recommendations = model_signal_recommendations(signal_analysis)
green_corridors = model_green_wave_corridors(coordination_pairs, _sensor_positions_raw)
print(f"[server] Signal intelligence: {city_summary['pct_needs_adaptive']}% need adaptive, {len(green_corridors)} corridors")

print(f"[server] {len(sensor_ids)} sensors | {len(timestamps):,} timestamps loaded")

# Track current WebSocket step for REST endpoints
_current_ws_step = 0

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Traffi6 — Karlsruhe Traffic Replay")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@app.get("/api/stats")
def api_stats():
    return database.get_stats()


@app.get("/api/timeline")
def api_timeline():
    return {
        "total_steps": len(timestamps),
        "current_step": 0,
        "current_timestamp": timestamps[0] if timestamps else None,
        "time_range": {
            "start": timestamps[0] if timestamps else None,
            "end": timestamps[-1] if timestamps else None,
        },
    }


@app.get("/api/sensors")
def api_sensors():
    return [
        {
            "sensor_id": sid,
            "lat": sensor_positions[sid][0],
            "lon": sensor_positions[sid][1],
            "total_volume": sensor_volumes.get(sid, 0),
        }
        for sid in sensor_ids
        if sid in sensor_positions
    ]


@app.get("/api/intelligence")
def api_intelligence():
    return {"peak_hours": peak_hours, "sensor_count": len(sensor_ids)}


@app.get("/api/traffic-status")
def api_traffic_status():
    """For mobile card -- returns current traffic conditions."""
    global _current_ws_step
    current_ts = timestamps[_current_ws_step] if timestamps else None
    readings = database.get_readings_at(current_ts) if current_ts else {}
    anomalies = detect_anomalies(readings, sensor_stats)
    status = compute_traffic_status(readings, sensor_stats)
    status["anomalies"] = anomalies
    status["timestamp"] = current_ts
    return status


@app.get("/api/signals")
def api_signals():
    """Per-sensor analysis (real) + recommendations (modeled)."""
    result = {}
    for sid, analysis in signal_analysis.items():
        entry = dict(analysis)
        if sid in _sensor_positions_raw:
            entry["lat"] = _sensor_positions_raw[sid][0]
            entry["lon"] = _sensor_positions_raw[sid][1]
        if sid in signal_recommendations:
            entry["recommendation"] = signal_recommendations[sid]
        result[sid] = entry
    return result


@app.get("/api/corridors")
def api_corridors():
    return green_corridors


@app.get("/api/city-summary")
def api_city_summary():
    return city_summary


# ---------------------------------------------------------------------------
# WebSocket streaming
# ---------------------------------------------------------------------------

TICKS_PER_TIMESTAMP = 20   # 20 ticks between data updates → vehicles drive ~2 sec before new counts
DEFAULT_FRAME_INTERVAL = 0.1  # 100 ms → 10 fps


@app.websocket("/ws/traffic")
async def ws_traffic(ws: WebSocket):
    await ws.accept()

    # Start at first timestamp with meaningful traffic (skip empty late-night data)
    ts_index = _start_index
    tick_count = 0
    speed_multiplier = 1.0
    paused = False
    readings = {}
    current_anomalies = []

    try:
        while True:
            # --- Handle incoming control messages (non-blocking) ----------
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=0.001)
                msg = json.loads(raw)
                if "speed" in msg:
                    speed_multiplier = max(0.1, float(msg["speed"]))
                if "jump_to" in msg:
                    ts_index = max(0, min(int(msg["jump_to"]), len(timestamps) - 1))
                    tick_count = 0
                if "pause" in msg:
                    paused = bool(msg["pause"])
            except (asyncio.TimeoutError, ValueError):
                pass

            if paused:
                await asyncio.sleep(0.05)
                continue

            if not timestamps:
                await ws.send_json({"error": "no data", "positions": []})
                await asyncio.sleep(1)
                continue

            # --- Feed real data based on speed-adjusted tick rate ----------
            # Speed controls how many timestamps pass per second, NOT fps
            # At 1x: 1 timestamp per 2 seconds (20 ticks × 0.1s)
            # At 10x: 10 timestamps per 2 seconds
            effective_ticks = max(2, int(TICKS_PER_TIMESTAMP / speed_multiplier))

            if tick_count % effective_ticks == 0:
                readings = database.get_readings_at(timestamps[ts_index])
                sim.update_from_data(readings)
                current_anomalies = detect_anomalies(readings, sensor_stats)

            sim.tick(0.1 * speed_multiplier)
            positions = sim.get_positions()

            global _current_ws_step
            _current_ws_step = ts_index

            await ws.send_json({
                "positions": positions,
                "timestamp": timestamps[ts_index],
                "step": ts_index,
                "total_steps": len(timestamps),
                "anomalies": current_anomalies,
            })

            tick_count += 1
            if tick_count >= effective_ticks:
                tick_count = 0
                ts_index = (ts_index + 1) % len(timestamps)

            # Always 10fps — speed is handled by faster timestamp advancement
            await asyncio.sleep(DEFAULT_FRAME_INTERVAL)

    except WebSocketDisconnect:
        pass


# ---------------------------------------------------------------------------
# Static files — serve frontend (mount LAST so API routes take priority)
# ---------------------------------------------------------------------------

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend')
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
